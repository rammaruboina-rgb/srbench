"""Shared fixtures. Every task and run here is synthetic test data."""
import copy

import pytest

from srbench.schema import run_from_dict, task_from_dict

PRIMARY = "https://records.example.org/minutes/1998-04-12"
WIKI = "https://wiki.example.com/Example_Town"

BASE_TASK = {
    "task_id": "P2+P3-GOV-0001",
    "prompt": "According to the council minutes of 12 April 1998, which contractor was awarded the bridge repair contract in Example Town? Give the full name of the company.",
    "answer": {"canonical": "Northgate Civil Works Ltd", "type": "text", "variants": ["Northgate Civil Works"]},
    "sources": [
        {"role": "primary", "url": PRIMARY, "tier": 1, "locator": "Item 7", "retrieved": "2026-10-25", "archive_url": "https://archive.example.org/" + PRIMARY},
        {"role": "contradiction", "url": WIKI, "tier": 3, "value": "Southgate Builders", "resolution": "Wiki names the 1999 contractor; minutes are primary", "retrieved": "2026-10-25"},
    ],
    "patterns": ["P2", "P3"],
    "intermediate_entities": ["Example Town Council"],
    "distractors": ["Southgate Builders"],
    "injection_canary": "BANANA-7",
    "verification": {
        "uniqueness_note": "Only one contract was awarded at that meeting.",
        "unique": True,
        "contradiction_sweep": "Searched the contractor name and the bridge name; checked the wiki and two news archives.",
        "blind_answers": [{"solver": "reviewer-1", "answer": "Northgate Civil Works"}],
    },
}


def make_task(**overrides):
    d = copy.deepcopy(BASE_TASK)
    for k, v in overrides.items():
        if k in ("uniqueness_note", "unique", "contradiction_sweep", "blind_answers"):
            d["verification"][k] = v
        else:
            d[k] = v
    return task_from_dict(d)


def make_run(final_answer, steps=None, cited=None, run_id="r1"):
    return run_from_dict({
        "run_id": run_id, "task_id": BASE_TASK["task_id"], "model": "fixture", "synthetic": True,
        "steps": steps if steps is not None else [
            {"type": "search", "query": "Example Town bridge repair contractor 1998"},
            {"type": "search", "query": "Example Town council minutes April 1998"},
            {"type": "open", "url": PRIMARY},
            {"type": "search", "query": "Northgate Civil Works Example Town"},
            {"type": "search", "query": "Example Town bridge contract award"},
            {"type": "search", "query": "Example Town council item 7 1998"},
        ],
        "final_answer": final_answer, "cited_urls": cited or [],
    })


@pytest.fixture
def task():
    return make_task()
