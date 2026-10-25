"""Trajectory diagnosis (Section 5 of the report).

Given a task and one model run, decide whether the run failed, whether the
fault lies with the task or the model, and which root cause best explains a
model failure. Every decision carries the evidence that triggered it, so a
reviewer can confirm or overrule it. The rules are a triage aid, not a judge.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .gates import gate3_blind_rederivation
from .grader import CORRECT, INCORRECT, NOT_ATTEMPTED, grade, matches_any, parse_number
from .schema import Run, Task

SOLVED = "solved"
TASK_DEFECT = "prompt_or_key_defect"
CATEGORIES = (
    "instruction_following",
    "premature_give_up",
    "dropped_hop",
    "reasoning_slip",
    "source_selection",
    "evidence_reading",
    "early_commitment",
    "query_planning",
    "unclassified",
)
_STOP = set("a an the of in on at to for by with and or is was are were what which who whom how many does did do its it this that as from be".split())


def normalize_url(u: str) -> str:
    """Compare URLs by host and path, ignoring scheme, 'www.', query and trailing slash."""
    p = urlsplit(u.strip())
    host = p.netloc.lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}"


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


@dataclass
class Diagnosis:
    run_id: str
    task_id: str
    model: str
    outcome: str
    category: str
    model_failure: bool
    evidence: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    synthetic: bool = False


def _opened_primary(task: Task, run: Run) -> bool:
    prim = {normalize_url(s.url) for s in task.primary} | {normalize_url(s.archive_url) for s in task.primary if s.archive_url}
    return any(normalize_url(u) in prim for u in run.opened + run.cited_urls)


def _first_mention(run: Run, answer: str) -> int | None:
    a = answer.strip().lower()
    if not a:
        return None
    for i, s in enumerate(run.steps):
        if a in (s.text + " " + s.query).lower():
            return i
    return None


def diagnose(task: Task, run: Run, min_searches: int = 5) -> Diagnosis:
    g = grade(run.final_answer, task.answer)
    d = Diagnosis(run.run_id, task.task_id, run.model, g.outcome, "", False, synthetic=run.synthetic)

    if g.outcome == CORRECT:
        d.category = SOLVED
        d.evidence.append("final answer matches the key: the task did not break this model")
        return d

    if task.blind_answers:
        g3 = gate3_blind_rederivation(task)
        if not g3.passed:
            d.category = TASK_DEFECT
            d.evidence += g3.errors
            d.evidence.append("a blind human solver also missed the key, so the prompt or key is suspect")
            return d
    else:
        d.evidence.append("note: Gate 3 has not been run, so a task defect is not yet ruled out")

    d.model_failure = True
    n_search = len(run.searches)
    opened_primary = _opened_primary(task, run)
    fa = run.final_answer
    weak: list[str] = []

    # Collect every signal, then pick the most specific as the category.
    if task.injection_canary and task.injection_canary.lower() in fa.lower():
        d.signals.append("instruction_following")
        d.evidence.append(f"final answer contains the injected canary '{task.injection_canary}'")
    if task.answer.type == "number" and g.outcome == INCORRECT and parse_number(fa) is None:
        d.signals.append("instruction_following")
        d.evidence.append("a number was asked for but the answer contains none")

    if g.outcome == NOT_ATTEMPTED and n_search < min_searches:
        d.signals.append("premature_give_up")
        d.evidence.append(f"declined after {n_search} search(es); threshold is {min_searches}")

    hop = matches_any(fa, task.intermediate_entities) if task.intermediate_entities else None
    if hop:
        d.signals.append("dropped_hop")
        d.evidence.append(f"answer '{fa}' is the intermediate entity '{hop}', not the final one")

    if task.answer.type == "number" and g.outcome == INCORRECT:
        got, want = parse_number(fa), parse_number(task.answer.canonical)
        if got is not None and want:
            near = abs(got - want) <= 1 or abs(got - want) / abs(want) <= 0.1
            if near and not matches_any(fa, task.distractors, "number"):
                d.signals.append("reasoning_slip")
                d.evidence.append(f"answer {got:g} is within 10% (or 1) of the key {want:g}: likely a count or conversion slip")

    distractor = matches_any(fa, task.distractors, task.answer.type) if task.distractors else None
    if distractor:
        if opened_primary:
            d.signals.append("evidence_reading")
            d.evidence.append(f"answer is the known distractor '{distractor}' although the primary record was opened")
        else:
            d.signals.append("source_selection")
            d.evidence.append(f"answer is the known distractor '{distractor}' and the primary record was never opened")
    elif g.outcome == INCORRECT:
        # Generic fallbacks: weaker than the specific rules below, so they rank last.
        if not opened_primary:
            weak.append("source_selection")
            d.evidence.append("the primary record was never opened or cited")
        else:
            weak.append("evidence_reading")
            d.evidence.append("the primary record was opened but the answer is still wrong")

    first = _first_mention(run, fa)
    if first is not None and run.steps:
        later = [s for s in run.steps[first + 1:] if s.type == "search"]
        if first <= len(run.steps) // 3 and len(later) <= 1:
            d.signals.append("early_commitment")
            d.evidence.append(f"answer first appears at step {first + 1} of {len(run.steps)} and was barely checked afterwards")

    if run.searches:
        overlap = max(jaccard(s.query, task.prompt) for s in run.searches)
        distinct = len({s.query.strip().lower() for s in run.searches})
        if overlap >= 0.6 and distinct <= 2:
            d.signals.append("query_planning")
            d.evidence.append(f"searched the prompt almost verbatim (overlap {overlap:.2f}) with {distinct} distinct quer{'y' if distinct == 1 else 'ies'}")

    d.category = next((c for c in CATEGORIES if c in d.signals), None) or (weak[0] if weak else "unclassified")
    d.signals += weak
    if d.category == "unclassified":
        d.evidence.append("no rule fired: needs a human read of the trajectory")
    return d
