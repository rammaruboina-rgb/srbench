"""Command-line interface: validate, grade, diagnose, report."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .diagnose import diagnose
from .gates import check_task
from .grader import grade
from .report import to_markdown
from .schema import SchemaError, load_runs, load_tasks, run_issues


def _validate(a: argparse.Namespace) -> int:
    tasks = load_tasks(a.tasks)
    bad = 0
    for t in tasks.values():
        v = check_task(t)
        status = "ACCEPT" if v.accepted else "REJECT"
        print(f"{status}  {t.task_id}")
        for issue in v.structural:
            print(f"    structure: {issue}")
        for g in v.gates:
            mark = "pass" if g.passed else "FAIL"
            print(f"    gate {g.gate} {mark:4}  {g.name}")
            for e in g.errors:
                print(f"        error:   {e}")
            for w in g.warnings:
                print(f"        warning: {w}")
        bad += not v.accepted
    print(f"\n{len(tasks) - bad} accepted, {bad} rejected")
    return 1 if bad else 0


def _grade(a: argparse.Namespace) -> int:
    t = load_tasks(a.tasks)[a.task_id]
    g = grade(a.answer, t.answer)
    print(g.outcome + (f" ({g.detail})" if g.detail else ""))
    return 0


def _diagnose(a: argparse.Namespace) -> int:
    tasks = load_tasks(a.tasks)
    for r in load_runs(a.runs):
        for issue in run_issues(r):
            print(f"warning: run {r.run_id}: {issue}", file=sys.stderr)
        if r.task_id not in tasks:
            print(f"warning: run {r.run_id} refers to unknown task {r.task_id}", file=sys.stderr)
            continue
        d = diagnose(tasks[r.task_id], r, a.min_searches)
        if a.json:
            print(json.dumps(asdict(d)))
        else:
            tag = " [synthetic]" if d.synthetic else ""
            print(f"{d.run_id}{tag}: {d.outcome} -> {d.category}")
            for e in d.evidence:
                print(f"    - {e}")
    return 0


def _report(a: argparse.Namespace) -> int:
    tasks = load_tasks(a.tasks)
    diags = [diagnose(tasks[r.task_id], r, a.min_searches) for r in load_runs(a.runs) if r.task_id in tasks]
    sys.stdout.write(to_markdown(tasks, diags, a.k))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="srbench", description="Search-resistant benchmark task toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="check task records against the schema and the five gates")
    v.add_argument("tasks")
    v.set_defaults(fn=_validate)

    g = sub.add_parser("grade", help="grade one answer against a task's key")
    g.add_argument("tasks")
    g.add_argument("task_id")
    g.add_argument("answer")
    g.set_defaults(fn=_grade)

    for name, fn, helptext in (("diagnose", _diagnose, "diagnose each run"), ("report", _report, "pool report in Markdown")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("tasks")
        s.add_argument("runs")
        s.add_argument("--min-searches", type=int, default=5)
        if name == "diagnose":
            s.add_argument("--json", action="store_true")
        else:
            s.add_argument("-k", type=int, default=2, help="failures needed to count a task as a reliable breaker")
        s.set_defaults(fn=fn)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except (SchemaError, KeyError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
