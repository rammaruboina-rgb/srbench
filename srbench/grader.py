"""Answer normalisation and grading.

Outcomes follow SimpleQA's three-way scheme: ``correct``, ``incorrect`` and
``not_attempted``. Grading is deterministic so that two reviewers running the
same key on the same answer always agree.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .schema import Answer

CORRECT, INCORRECT, NOT_ATTEMPTED = "correct", "incorrect", "not_attempted"

_ABSTAIN = re.compile(
    r"\b(i\s+(do\s+not|don'?t)\s+know|unable\s+to\s+(find|determine|verify)|"
    r"could\s*n[o']?t\s+(find|determine|verify)|cannot\s+(find|determine|verify)|"
    r"not\s+(found|available|enough\s+information)|no\s+answer|unknown)\b",
    re.IGNORECASE,
)
_ARTICLES = re.compile(r"\b(a|an|the)\b")
_SMALL = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_SCALE = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})


def normalize_text(s: str) -> str:
    """Lower-case, strip accents, punctuation, articles and extra spaces."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = _ARTICLES.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _words_to_number(words: list[str]) -> float | None:
    total, current, seen = 0, 0, False
    for w in words:
        if w == "and":
            continue
        if w in _SMALL:
            current += _SMALL[w]
            seen = True
        elif w in _SCALE:
            current = max(current, 1) * _SCALE[w]
            if _SCALE[w] >= 1000:
                total, current = total + current, 0
            seen = True
        else:
            return None
    return float(total + current) if seen else None


def parse_number(s: str) -> float | None:
    """Parse '3,000', '3 000', '3000.0', '3k', '2.5 million' or 'three thousand'."""
    t = s.strip().lower()
    t = re.sub(r"(?<=\d)[,   ](?=\d{3}\b)", "", t)
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if m:
        value = float(m.group())
        rest = t[m.end():].strip()
        for word, mult in (("k", 1e3), ("thousand", 1e3), ("million", 1e6), ("m", 1e6), ("billion", 1e9), ("bn", 1e9)):
            if re.match(rf"{word}\b", rest):
                value *= mult
                break
        return value
    words = re.findall(r"[a-z]+", t.replace("-", " "))
    return _words_to_number(words) if words else None


def parse_date(s: str) -> str | None:
    """Return an ISO date string for '2025-01-24', '24 January 2025' or 'Jan 24, 2025'."""
    t = s.strip().lower().replace(",", " ")
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"\b(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})\b", t)
    if m and m.group(2)[:3] in _MONTHS:
        return f"{int(m.group(3)):04d}-{_MONTHS[m.group(2)[:3]]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"\b([a-z]+)\.?\s+(\d{1,2})\s+(\d{4})\b", t)
    if m and m.group(1)[:3] in _MONTHS:
        return f"{int(m.group(3)):04d}-{_MONTHS[m.group(1)[:3]]:02d}-{int(m.group(2)):02d}"
    return None


def is_abstention(answer: str) -> bool:
    return not answer.strip() or bool(_ABSTAIN.search(answer))


def _matches(candidate: str, key: Answer) -> bool:
    targets = [key.canonical, *key.variants]
    if key.type == "number":
        got = parse_number(candidate)
        if got is None:
            return False
        for t in targets:
            want = parse_number(t)
            if want is None:
                continue
            tol = abs(want) * key.rel_tol
            if abs(got - want) <= tol:
                return True
        return False
    if key.type == "date":
        got = parse_date(candidate)
        return got is not None and got in {parse_date(t) for t in targets}
    norm = normalize_text(candidate)
    return any(norm == normalize_text(t) for t in targets)


@dataclass(frozen=True)
class Grade:
    outcome: str
    detail: str = ""


def grade(candidate: str, key: Answer) -> Grade:
    """Grade one answer against a key. Abstentions are ``not_attempted``."""
    if _matches(candidate, key):
        return Grade(CORRECT)
    if is_abstention(candidate):
        return Grade(NOT_ATTEMPTED, "answer is empty or declines to answer")
    return Grade(INCORRECT)


def matches_any(candidate: str, values: list[str], answer_type: str = "text") -> str | None:
    """Return the first value the candidate matches, using the key's answer type."""
    for v in values:
        if _matches(candidate, Answer(canonical=v, type=answer_type)):
            return v
    return None
