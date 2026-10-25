# srbench

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23647111.svg)](https://doi.org/10.5281/zenodo.23647111)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Tests: 52 passing](https://img.shields.io/badge/tests-52%20passing-brightgreen)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Tools for authoring, verifying and diagnosing **search-resistant benchmark tasks** for AI research agents.
Reference implementation for the technical report *Designing Search-Resistant Benchmark Tasks for AI Research Agents*
(Maruboina, 2026; all versions: DOI [10.5281/zenodo.23647111](https://doi.org/10.5281/zenodo.23647111)).

Pure Python 3.9+, no dependencies. 52 tests, 90% line coverage.

## What it does

| Module | Report section | Job |
| --- | --- | --- |
| `schema.py` | 6 | Task and run records (JSON Lines), loading, structural checks |
| `grader.py` | 4, 5 | Deterministic grading: `correct` / `incorrect` / `not_attempted`; numbers, dates, text variants |
| `lint.py` | 4 (Gate 5) | Prompt ambiguity rules: time anchors, vague words, unscoped superlatives, answer leaks |
| `gates.py` | 4 | The five verification gates; a task is accepted only if all pass |
| `diagnose.py` | 5 | Trajectory triage: task defect vs model failure, plus one of 8 root-cause categories with evidence |
| `report.py` | 5 | Pool report: root causes, failure rate per pattern, reliable breakers, tasks to repair |

## Use

```bash
python -m srbench validate examples/patent_tasks.jsonl
python -m srbench diagnose examples/patent_tasks.jsonl examples/patent_runs.jsonl
python -m srbench report   examples/patent_tasks.jsonl examples/patent_runs.jsonl
python -m srbench grade    examples/hle_task.jsonl P4+P5-SCI-0001 "three thousand"
python -m pytest
```

## Data

| File | What it is |
| --- | --- |
| `examples/patent_tasks.jsonl` | 14 patent-record tasks (10 in round 1, 4 hardened in round 2), each verified against Google Patents records on 25–26 Oct 2026. All 14 pass Gates 1, 2, 4 and 5; Gate 3 (blind second solver) is open. **Retired**: published with answer keys. |
| `examples/patent_runs.jsonl` | **30 real runs** on 26 Oct 2026: ChatGPT web (14), Claude.ai web (14), Gemini web (2). Each has the extracted answer, the visible search steps and sources, and a short excerpt of the reply. All 30 are correct. |
| `examples/STALLS.md` | Gemini attempts that produced no answer (excluded from the run file). |
| `examples/hle_task.jsonl`, `hle_drafts.jsonl` | Worked example from arXiv version records of the Humanity's Last Exam paper, and its two rejected drafts. |
| `examples/hle_runs.synthetic.jsonl` | **Synthetic** trajectories used to test the diagnoser. Not real model runs. |
| `DEVLOG.md` | Real defects found in the toolkit and how each was fixed. |

## Key result

14 primary-sourced patent tasks, 30 real runs on ChatGPT, Claude.ai and Gemini (26 Oct 2026): **30 of 30 answers correct, 0 model failures.**
Verified and unambiguous is not enough: every task fell to one targeted search plus one page read. The runs also exposed two flaws
in the tasks themselves and one unsupported detail inside a correct answer. Details in Section 9 of the report.

## Limits

The diagnoser is a triage aid: its rules are simple and explainable, and a reviewer confirms every label.
Trajectories from consumer chat apps show only what the app displays (source labels, some queries).
Gate 3 needs a second person and cannot be self-certified.

## License

MIT

## How to cite

> Maruboina, R. K. (2026). *Designing Search-Resistant Benchmark Tasks for AI Research Agents* (v3). Zenodo. https://doi.org/10.5281/zenodo.23647111

```bibtex
@techreport{maruboina2026srbench,
  author      = {Maruboina, Rama Krishnudu},
  title       = {Designing Search-Resistant Benchmark Tasks for AI Research Agents},
  institution = {OpenTrain},
  type        = {Technical note},
  year        = {2026},
  version     = {v3},
  publisher   = {Zenodo},
  doi         = {10.5281/zenodo.23647111},
  url         = {https://doi.org/10.5281/zenodo.23647111}
}
```
