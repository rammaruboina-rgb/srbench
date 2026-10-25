from pathlib import Path

from conftest import PRIMARY, WIKI, make_run, make_task

from srbench.cli import main
from srbench.diagnose import SOLVED, TASK_DEFECT, diagnose, jaccard, normalize_url
from srbench.report import pool_summary, to_markdown
from srbench.schema import load_runs, load_tasks

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_normalize_url():
    assert normalize_url("https://www.Example.org/a/") == normalize_url("http://example.org/a?x=1")


def test_jaccard_bounds():
    assert jaccard("a b c", "a b c") == 1.0
    assert jaccard("", "") == 0.0


def test_solved(task):
    assert diagnose(task, make_run("Northgate Civil Works")).category == SOLVED


def test_task_defect_when_blind_solver_disagrees():
    t = make_task(blind_answers=[{"solver": "r2", "answer": "Southgate Builders"}])
    d = diagnose(t, make_run("Southgate Builders"))
    assert d.category == TASK_DEFECT and not d.model_failure


def test_instruction_following_canary(task):
    assert diagnose(task, make_run("BANANA-7")).category == "instruction_following"


def test_premature_give_up(task):
    run = make_run("I could not find it", steps=[{"type": "search", "query": "bridge contractor"}])
    assert diagnose(task, run).category == "premature_give_up"


def test_dropped_hop(task):
    assert diagnose(task, make_run("Example Town Council")).category == "dropped_hop"


def test_distractor_without_primary_is_source_selection(task):
    run = make_run("Southgate Builders", steps=[
        {"type": "search", "query": "Example Town bridge contractor"},
        {"type": "open", "url": WIKI}], cited=[WIKI])
    assert diagnose(task, run).category == "source_selection"


def test_distractor_with_primary_is_evidence_reading(task):
    run = make_run("Southgate Builders", steps=[
        {"type": "search", "query": "Example Town minutes 1998"},
        {"type": "open", "url": PRIMARY},
        {"type": "search", "query": "Example Town contractor"},
        {"type": "search", "query": "Example Town bridge 1999"}])
    assert diagnose(task, run).category == "evidence_reading"


def test_reasoning_slip_on_numbers():
    t = make_task(answer={"canonical": "48", "type": "number"}, distractors=[], intermediate_entities=[],
                  blind_answers=[{"solver": "reviewer-1", "answer": "48"}],
                  prompt="How many votes did the motion receive at the 12 April 1998 meeting? Answer with a number.")
    run = make_run("47")
    assert diagnose(t, run).category == "reasoning_slip"


def test_early_commitment(task):
    run = make_run("Eastgate Paving", steps=[
        {"type": "search", "query": "Example Town bridge contractor"},
        {"type": "think", "text": "Probably Eastgate Paving."},
        {"type": "open", "url": PRIMARY},
        {"type": "think", "text": "Going with it."},
        {"type": "think", "text": "Done."},
        {"type": "think", "text": "Final."}])
    assert "early_commitment" in diagnose(task, run).signals


def test_query_planning_signal(task):
    run = make_run("Eastgate Paving", steps=[{"type": "search", "query": task.prompt}])
    assert "query_planning" in diagnose(task, run).signals


def test_hle_synthetic_runs_match_expected_categories():
    tasks = load_tasks(EXAMPLES / "hle_task.jsonl")
    runs = load_runs(EXAMPLES / "hle_runs.synthetic.jsonl")
    got = {r.run_id: diagnose(tasks[r.task_id], r).category for r in runs}
    assert got == {"syn-A": "source_selection", "syn-B": "evidence_reading",
                   "syn-C": "premature_give_up", "syn-D": SOLVED}


def test_report_and_cli(capsys):
    tasks = load_tasks(EXAMPLES / "hle_task.jsonl")
    runs = load_runs(EXAMPLES / "hle_runs.synthetic.jsonl")
    diags = [diagnose(tasks[r.task_id], r) for r in runs]
    s = pool_summary(tasks, diags, k=2)
    assert s["reliable_breakers"] == ["P4+P5-SCI-0001"] and s["synthetic_runs"] == 4
    assert "synthetic test fixtures" in to_markdown(tasks, diags)
    assert main(["validate", str(EXAMPLES / "hle_task.jsonl")]) == 1
    assert main(["grade", str(EXAMPLES / "hle_task.jsonl"), "P4+P5-SCI-0001", "three thousand"]) == 0
    assert "correct" in capsys.readouterr().out
    assert main(["validate", "missing.jsonl"]) == 2


def test_specific_rules_outrank_generic_fallback(task):
    # Regression for DEVLOG item 4: a verbatim one-query run that never opens the
    # primary record is a query-planning failure first, not just "wrong source".
    run = make_run("Eastgate Paving", steps=[{"type": "search", "query": task.prompt}])
    d = diagnose(task, run)
    assert d.category == "query_planning"
    assert "source_selection" in d.signals


def test_real_patent_runs_are_all_solved():
    # 30 real runs on 26 Oct 2026 (ChatGPT 14, Claude.ai 14, Gemini 2): every answer matches its key.
    tasks = load_tasks(EXAMPLES / "patent_tasks.jsonl")
    runs = load_runs(EXAMPLES / "patent_runs.jsonl")
    assert len(tasks) == 14 and len(runs) == 30 and not any(r.synthetic for r in runs)
    assert {diagnose(tasks[r.task_id], r).category for r in runs} == {SOLVED}
