"""The five verification gates (Section 4 of the report).

A task enters the pool only when every gate passes. Gates run in order and
each returns a GateResult; warnings never block, errors always do.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .grader import CORRECT, grade
from .lint import ERROR, lint_prompt
from .schema import Task, structural_issues


@dataclass
class GateResult:
    gate: int
    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def gate1_primary_source(t: Task) -> GateResult:
    r = GateResult(1, "Seed from a primary record", True)
    prim = t.primary
    if not prim:
        r.errors.append("no source with role 'primary'")
    for s in prim:
        if s.tier == 3:
            r.errors.append(f"primary source is Tier 3 (aggregator): {s.url}")
        if not s.locator:
            r.errors.append(f"primary source has no locator (page, section or paragraph): {s.url}")
        if not s.retrieved:
            r.errors.append(f"primary source has no retrieval date: {s.url}")
        if not s.archive_url:
            r.warnings.append(f"no archive snapshot for {s.url}; the page may change")
    if prim and all(s.tier == 2 for s in prim):
        if not any(s.role == "cross_check" and s.tier <= 2 for s in t.sources):
            r.errors.append("Tier 2 primary source needs a Tier 1 or Tier 2 cross-check")
    r.passed = not r.errors
    return r


def gate2_uniqueness(t: Task) -> GateResult:
    r = GateResult(2, "Uniqueness check", True)
    if not t.uniqueness_note.strip():
        r.errors.append("no uniqueness note: record how you searched for a second valid answer")
    if t.unique is False:
        r.errors.append("reviewer found more than one valid answer: tighten the prompt")
    elif t.unique is None:
        r.errors.append("uniqueness not confirmed: set verification.unique after the search")
    if not t.distractors:
        r.warnings.append("no distractors recorded; list the near-miss answers you ruled out")
    for d in t.distractors:
        if grade(d, t.answer).outcome == CORRECT:
            r.errors.append(f"distractor '{d}' is graded correct by the key; key and distractor overlap")
    r.passed = not r.errors
    return r


def gate3_blind_rederivation(t: Task) -> GateResult:
    r = GateResult(3, "Blind re-derivation", True)
    if not t.blind_answers:
        r.errors.append("no blind second-solver answer recorded")
    for b in t.blind_answers:
        g = grade(b.get("answer", ""), t.answer)
        if g.outcome != CORRECT:
            r.errors.append(f"blind solver {b.get('solver', '?')} answered '{b.get('answer', '')}' ({g.outcome})")
    r.passed = not r.errors
    return r


def gate4_contradictions(t: Task) -> GateResult:
    r = GateResult(4, "Contradiction sweep", True)
    if not t.contradiction_sweep.strip():
        r.errors.append("no contradiction sweep recorded: list the searches used to look for conflicting values")
    for c in t.contradictions:
        if not c.value:
            r.errors.append(f"contradiction {c.url} has no conflicting value recorded")
        if not c.resolution.strip():
            r.errors.append(f"contradiction {c.url} is unresolved")
    r.passed = not r.errors
    return r


def gate5_ambiguity(t: Task) -> GateResult:
    r = GateResult(5, "Ambiguity and stability", True)
    for f in lint_prompt(t):
        (r.errors if f.severity == ERROR else r.warnings).append(f"[{f.rule}] {f.message}")
    r.passed = not r.errors
    return r


GATES = (gate1_primary_source, gate2_uniqueness, gate3_blind_rederivation, gate4_contradictions, gate5_ambiguity)


@dataclass
class TaskVerdict:
    task_id: str
    structural: list[str]
    gates: list[GateResult]

    @property
    def accepted(self) -> bool:
        return not self.structural and all(g.passed for g in self.gates)

    @property
    def first_failure(self) -> GateResult | None:
        return next((g for g in self.gates if not g.passed), None)


def check_task(t: Task) -> TaskVerdict:
    return TaskVerdict(t.task_id, structural_issues(t), [g(t) for g in GATES])
