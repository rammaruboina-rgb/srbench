from pathlib import Path

from conftest import make_task

from srbench.gates import check_task
from srbench.lint import lint_prompt
from srbench.schema import load_tasks, structural_issues

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def rules(t):
    return {f.rule for f in lint_prompt(t)}


def test_clean_fixture_is_accepted(task):
    v = check_task(task)
    assert v.accepted, [(g.name, g.errors) for g in v.gates]


def test_lint_catches_unanchored_time_words():
    assert "time-anchor" in rules(make_task(prompt="Who is the current mayor of Example Town?"))
    assert "time-anchor" not in rules(make_task(prompt="Who was the mayor of Example Town as of 1 May 1998?"))


def test_lint_p4_needs_anchor():
    t = make_task(prompt="How many questions does the benchmark contain?", patterns=["P4"])
    assert "p4-anchor" in rules(t)


def test_lint_no_false_positives_on_how_many_or_names():
    # Regression for DEVLOG items 1 and 2.
    t = make_task(prompt="How many questions did Humanity's Last Exam contain in v1? Answer with a number.")
    assert "vague-word" not in rules(t)
    assert "unscoped-superlative" not in rules(t)


def test_lint_flags_two_questions_and_answer_leak():
    assert "one-question" in rules(make_task(prompt="Who won? And when?"))
    assert "answer-leak" in rules(make_task(prompt="Was it Northgate Civil Works Ltd that won the 1998 contract?"))


def test_gate_failures_are_specific():
    assert check_task(make_task(blind_answers=[{"solver": "r2", "answer": "Southgate Builders"}])).first_failure.gate == 3
    assert check_task(make_task(unique=False)).first_failure.gate == 2
    assert check_task(make_task(distractors=["Northgate Civil Works"])).first_failure.gate == 2


def test_tier3_primary_and_unresolved_contradiction_fail():
    t = make_task()
    t.sources[0].tier = 3
    assert not check_task(t).gates[0].passed
    t = make_task()
    t.sources[1].resolution = ""
    assert not check_task(t).gates[3].passed


def test_structural_issues():
    t = make_task(task_id="bad id", patterns=["P9"])
    issues = " ".join(structural_issues(t))
    assert "task_id" in issues and "P9" in issues


def test_hle_drafts_fail_where_expected():
    drafts = load_tasks(EXAMPLES / "hle_drafts.jsonl")
    d1 = check_task(drafts["P4+P5-SCI-0901"])
    assert [g.gate for g in d1.gates if not g.passed] == [2, 3, 4, 5]
    d2 = check_task(drafts["P4+P5-SCI-0902"])
    assert [g.gate for g in d2.gates if not g.passed] == [2, 3]


def test_hle_final_only_waits_on_gate3():
    final = check_task(load_tasks(EXAMPLES / "hle_task.jsonl")["P4+P5-SCI-0001"])
    assert [g.gate for g in final.gates if not g.passed] == [3]


def test_answer_leak_needs_whole_token():
    # Regression for DEVLOG item 5: "19" inside "1972" is not a leak.
    t = make_task(prompt="How many claims does the patent granted on 12 September 1972 contain? Answer with a number.",
                  answer={"canonical": "19", "type": "number"})
    assert "answer-leak" not in rules(t)
    t = make_task(prompt="Does the patent have 19 claims? Answer with a number.", answer={"canonical": "19", "type": "number"})
    assert "answer-leak" in rules(t)


def test_patent_pool_waits_only_on_gate3():
    for t in load_tasks(EXAMPLES / "patent_tasks.jsonl").values():
        v = check_task(t)
        assert [g.gate for g in v.gates if not g.passed] == [3], t.task_id
