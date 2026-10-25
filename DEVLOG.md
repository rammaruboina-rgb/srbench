# Development log

Real defects found while building and testing srbench, with the fix for each.

| # | Found by | Failure | Root cause | Fix |
| --- | --- | --- | --- | --- |
| 1 | `srbench validate` on the HLE drafts | "how many" was flagged as a vague word | the vague-word rule matched "many" anywhere | negative look-behind: `(?<!how )many` |
| 2 | `srbench validate` on the HLE drafts | "Last" in "Humanity's Last Exam" was flagged as an unscoped superlative | the rule was case-insensitive, so proper names matched | match lower-case superlatives only |
| 3 | `pytest` (test_reasoning_slip_on_numbers) | a numeric slip (47 vs 48) was labelled `prompt_or_key_defect` | the test changed the answer key but kept the old blind answer, so Gate 3 disagreed; the tool was right to blame the task | updated the fixture's blind answer; kept the behaviour, since it is the point of Gate 3 |
| 4 | design review while writing Section 7 | `early_commitment` and `query_planning` could never be the main label for a wrong answer | the generic rule "primary record not opened / opened but wrong" fired for every wrong answer and ranked above them | split rules into specific and generic; generic ones rank last but stay recorded as signals |
| 5 | `srbench validate` on the patent tasks | "19" (the answer) reported as leaked in a prompt containing "1972" | the answer-leak rule used plain substring search | whole-token match with look-arounds |
