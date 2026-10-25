"""Prompt ambiguity linter (Gate 5).

Each rule returns findings with a severity: ``error`` blocks a task,
``warning`` asks a reviewer to look. Rules are deliberately simple and
explainable; they catch the wording problems that most often let a model
give a defensible "wrong" answer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import Task

ERROR, WARNING = "error", "warning"

_YEAR = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
_ANCHOR = re.compile(r"\b(as of|in \d{4}|on \d{1,2} \w+ \d{4}|version|v\d+\b|edition|at the time of)", re.I)
_RELATIVE_TIME = re.compile(r"\b(current(ly)?|latest|now|today|recent(ly)?|most recent|still|nowadays|this year|so far)\b", re.I)
_VAGUE = re.compile(r"\b(about|approximately|around|roughly|several|(?<!how )many|some|famous|well[- ]known|popular)\b", re.I)
# Lower-case only: capitalised words such as "Last" in "Humanity's Last Exam" are names, not superlatives.
_SUPERLATIVE = re.compile(r"\b(first|last|largest|smallest|biggest|oldest|newest|earliest|highest|lowest|only)\b")
_FORMAT_CUE = re.compile(r"\b(answer with|give (the|a|an|only)|reply with|in the format|as a number|yyyy|full name|name of|how many|which year|what year|what date)\b", re.I)


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str


def lint_prompt(task: Task, max_words: int = 120) -> list[Finding]:
    p = task.prompt
    out: list[Finding] = []

    if p.count("?") > 1:
        out.append(Finding("one-question", ERROR, "prompt asks more than one question; split it or merge into one ask"))

    has_anchor = bool(_YEAR.search(p) or _ANCHOR.search(p))
    if _RELATIVE_TIME.search(p) and not has_anchor:
        word = _RELATIVE_TIME.search(p).group(0)
        out.append(Finding("time-anchor", ERROR, f"'{word}' with no date anchor: the answer can change after publication"))
    if "P4" in task.patterns and not has_anchor:
        out.append(Finding("p4-anchor", ERROR, "P4 task without an explicit date, year or version anchor"))

    m = _VAGUE.search(p)
    if m:
        out.append(Finding("vague-word", WARNING, f"vague word '{m.group(0)}' invites more than one reading"))

    m = _SUPERLATIVE.search(p)
    if m and not re.search(r"\b(in|of|among|within|by|for)\b", p[m.end():], re.I):
        out.append(Finding("unscoped-superlative", WARNING, f"'{m.group(0)}' has no scope (in what set, place or period?)"))

    if not _FORMAT_CUE.search(p) and task.answer.type in ("number", "date"):
        out.append(Finding("answer-format", WARNING, f"{task.answer.type} answer but the prompt does not state the format"))

    n_words = len(p.split())
    if n_words > max_words:
        out.append(Finding("length", WARNING, f"prompt is {n_words} words; long prompts hide ambiguity"))

    # Whole-token match only: "19" must not match inside "1972" (DEVLOG item 5).
    if task.answer.canonical and re.search(rf"(?<![\w,.]){re.escape(task.answer.canonical.lower())}(?![\w]|[,.]\d)", p.lower()):
        out.append(Finding("answer-leak", ERROR, "the answer text appears in the prompt"))
    return out
