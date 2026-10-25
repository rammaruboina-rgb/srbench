"""Aggregate diagnoses into a pool report (Markdown)."""
from __future__ import annotations

from collections import Counter, defaultdict

from .diagnose import SOLVED, TASK_DEFECT, Diagnosis
from .schema import PATTERNS, Task


def pool_summary(tasks: dict[str, Task], diags: list[Diagnosis], k: int = 2) -> dict:
    by_task: dict[str, list[Diagnosis]] = defaultdict(list)
    for d in diags:
        by_task[d.task_id].append(d)
    reliable = sorted(t for t, ds in by_task.items() if sum(d.model_failure for d in ds) >= k)
    per_pattern: dict[str, list[int]] = {p: [0, 0] for p in PATTERNS}
    for d in diags:
        if d.task_id not in tasks:
            continue
        for p in tasks[d.task_id].patterns:
            per_pattern[p][1] += 1
            per_pattern[p][0] += int(d.model_failure)
    return {
        "runs": len(diags),
        "synthetic_runs": sum(d.synthetic for d in diags),
        "categories": Counter(d.category for d in diags),
        "reliable_breakers": reliable,
        "per_pattern": {p: v for p, v in per_pattern.items() if v[1]},
        "defects": sorted({d.task_id for d in diags if d.category == TASK_DEFECT}),
        "too_easy": sorted({d.task_id for d in diags if d.category == SOLVED}),
    }


def to_markdown(tasks: dict[str, Task], diags: list[Diagnosis], k: int = 2) -> str:
    s = pool_summary(tasks, diags, k)
    lines = ["# Pool report", ""]
    if s["synthetic_runs"]:
        lines += [f"> {s['synthetic_runs']} of {s['runs']} runs are synthetic test fixtures, not real model runs.", ""]
    lines += ["| Run | Task | Model | Outcome | Category | Evidence |", "| --- | --- | --- | --- | --- | --- |"]
    for d in diags:
        ev = "; ".join(d.evidence).replace("|", "/")
        lines.append(f"| {d.run_id} | {d.task_id} | {d.model} | {d.outcome} | {d.category} | {ev} |")
    lines += ["", "## Root causes", "", "| Category | Runs |", "| --- | --- |"]
    lines += [f"| {c} | {n} |" for c, n in s["categories"].most_common()]
    lines += ["", "## Failure rate by pattern", "", "| Pattern | Model failures / runs |", "| --- | --- |"]
    lines += [f"| {p} {PATTERNS[p]} | {f} / {n} |" for p, (f, n) in s["per_pattern"].items()]
    lines += ["", f"Tasks failed by at least {k} runs: {', '.join(s['reliable_breakers']) or 'none'}",
              f"Tasks needing repair (prompt or key): {', '.join(s['defects']) or 'none'}",
              f"Tasks solved at least once (consider strengthening): {', '.join(s['too_easy']) or 'none'}"]
    return "\n".join(lines) + "\n"
