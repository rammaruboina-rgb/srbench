"""Task and run records, loading, and structural validation.

A *task* is one benchmark item with its answer key and verification record.
A *run* is one model attempt at a task: its search trajectory and final answer.
Both are stored as JSON Lines (one JSON object per line).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

PATTERNS = {
    "P1": "Inverted multi-constraint",
    "P2": "Multi-hop record chain",
    "P3": "Primary-record only",
    "P4": "Temporal anchoring",
    "P5": "Popular error vs primary source",
    "P6": "Reasoning traps and injected text",
}
ANSWER_TYPES = {"text", "number", "date"}
SOURCE_ROLES = {"primary", "cross_check", "contradiction"}
STEP_TYPES = {"search", "open", "think"}

_URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TASK_ID = re.compile(r"^P[1-6](\+P[1-6])*-[A-Z0-9]+-\d{4}$")


@dataclass
class Source:
    url: str
    role: str = "primary"
    tier: int = 1
    locator: str = ""
    retrieved: str = ""
    archive_url: str = ""
    value: str = ""
    resolution: str = ""


@dataclass
class Answer:
    canonical: str
    type: str = "text"
    variants: list[str] = field(default_factory=list)
    unit: str = ""
    rel_tol: float = 0.0


@dataclass
class Task:
    task_id: str
    prompt: str
    answer: Answer
    sources: list[Source]
    patterns: list[str]
    solution_path: list[str] = field(default_factory=list)
    intended_failure: str = ""
    uniqueness_note: str = ""
    unique: bool | None = None
    contradiction_sweep: str = ""
    blind_answers: list[dict[str, str]] = field(default_factory=list)
    intermediate_entities: list[str] = field(default_factory=list)
    distractors: list[str] = field(default_factory=list)
    injection_canary: str = ""
    as_of: str = ""

    @property
    def primary(self) -> list[Source]:
        return [s for s in self.sources if s.role == "primary"]

    @property
    def contradictions(self) -> list[Source]:
        return [s for s in self.sources if s.role == "contradiction"]


@dataclass
class Step:
    type: str
    query: str = ""
    url: str = ""
    text: str = ""


@dataclass
class Run:
    run_id: str
    task_id: str
    model: str
    steps: list[Step]
    final_answer: str
    cited_urls: list[str] = field(default_factory=list)
    synthetic: bool = False

    @property
    def searches(self) -> list[Step]:
        return [s for s in self.steps if s.type == "search"]

    @property
    def opened(self) -> list[str]:
        return [s.url for s in self.steps if s.type == "open" and s.url]


class SchemaError(ValueError):
    """Raised when a record cannot be parsed into a Task or Run."""


def _require(obj: dict[str, Any], key: str, where: str) -> Any:
    if key not in obj or obj[key] in (None, "", []):
        raise SchemaError(f"{where}: missing required field '{key}'")
    return obj[key]


def task_from_dict(d: dict[str, Any]) -> Task:
    where = f"task {d.get('task_id', '?')}"
    a = _require(d, "answer", where)
    if isinstance(a, str):
        a = {"canonical": a}
    answer = Answer(
        canonical=str(_require(a, "canonical", where + ".answer")),
        type=a.get("type", "text"),
        variants=[str(v) for v in a.get("variants", [])],
        unit=a.get("unit", ""),
        rel_tol=float(a.get("rel_tol", 0.0)),
    )
    sources = [Source(**s) for s in _require(d, "sources", where)]
    v = d.get("verification", {})
    return Task(
        task_id=_require(d, "task_id", where),
        prompt=_require(d, "prompt", where),
        answer=answer,
        sources=sources,
        patterns=list(_require(d, "patterns", where)),
        solution_path=list(d.get("solution_path", [])),
        intended_failure=d.get("intended_failure", ""),
        uniqueness_note=v.get("uniqueness_note", ""),
        unique=v.get("unique"),
        contradiction_sweep=v.get("contradiction_sweep", ""),
        blind_answers=list(v.get("blind_answers", [])),
        intermediate_entities=list(d.get("intermediate_entities", [])),
        distractors=[str(x) for x in d.get("distractors", [])],
        injection_canary=d.get("injection_canary", ""),
        as_of=v.get("as_of", d.get("as_of", "")),
    )


def run_from_dict(d: dict[str, Any]) -> Run:
    where = f"run {d.get('run_id', '?')}"
    steps = [Step(**s) for s in d.get("steps", [])]
    return Run(
        run_id=_require(d, "run_id", where),
        task_id=_require(d, "task_id", where),
        model=d.get("model", "unknown"),
        steps=steps,
        final_answer=str(d.get("final_answer", "")),
        cited_urls=list(d.get("cited_urls", [])),
        synthetic=bool(d.get("synthetic", False)),
    )


def read_jsonl(path: str | Path) -> Iterable[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise SchemaError(f"{path}:{n}: invalid JSON ({e.msg})") from e


def load_tasks(path: str | Path) -> dict[str, Task]:
    tasks: dict[str, Task] = {}
    for d in read_jsonl(path):
        t = task_from_dict(d)
        if t.task_id in tasks:
            raise SchemaError(f"duplicate task_id {t.task_id}")
        tasks[t.task_id] = t
    return tasks


def load_runs(path: str | Path) -> list[Run]:
    return [run_from_dict(d) for d in read_jsonl(path)]


def structural_issues(t: Task) -> list[str]:
    """Problems that make a task record malformed, independent of the five gates."""
    issues: list[str] = []
    if not _TASK_ID.match(t.task_id):
        issues.append(f"task_id '{t.task_id}' should look like P4-SCI-0001 (pattern-domain-number)")
    if t.answer.type not in ANSWER_TYPES:
        issues.append(f"answer.type '{t.answer.type}' not in {sorted(ANSWER_TYPES)}")
    bad = [p for p in t.patterns if p not in PATTERNS]
    if bad:
        issues.append(f"unknown pattern tags {bad}; use P1-P6")
    for i, s in enumerate(t.sources):
        if s.role not in SOURCE_ROLES:
            issues.append(f"sources[{i}].role '{s.role}' not in {sorted(SOURCE_ROLES)}")
        if not _URL.match(s.url):
            issues.append(f"sources[{i}].url is not an http(s) URL")
        if s.tier not in (1, 2, 3):
            issues.append(f"sources[{i}].tier must be 1, 2 or 3")
        if s.retrieved and not _ISO_DATE.match(s.retrieved):
            issues.append(f"sources[{i}].retrieved must be YYYY-MM-DD")
    if t.as_of and not _ISO_DATE.match(t.as_of):
        issues.append("verification.as_of must be YYYY-MM-DD")
    return issues


def run_issues(r: Run) -> list[str]:
    issues = []
    for i, s in enumerate(r.steps):
        if s.type not in STEP_TYPES:
            issues.append(f"steps[{i}].type '{s.type}' not in {sorted(STEP_TYPES)}")
        if s.type == "search" and not s.query:
            issues.append(f"steps[{i}] is a search with no query")
        if s.type == "open" and not s.url:
            issues.append(f"steps[{i}] opens no url")
    return issues
