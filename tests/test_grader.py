import pytest

from srbench.grader import CORRECT, INCORRECT, NOT_ATTEMPTED, grade, normalize_text, parse_date, parse_number
from srbench.schema import Answer


@pytest.mark.parametrize("s,want", [
    ("3,000", 3000), ("3000", 3000), ("3 000", 3000), ("3,000.5", 3000.5),
    ("3k", 3000), ("2.5 million", 2_500_000), ("three thousand", 3000),
    ("twenty-one", 21), ("one hundred and five", 105), ("about 1,266 questions", 1266),
    ("none", None),
])
def test_parse_number(s, want):
    assert parse_number(s) == want


@pytest.mark.parametrize("s,want", [
    ("2025-01-24", "2025-01-24"), ("24 January 2025", "2025-01-24"),
    ("January 24, 2025", "2025-01-24"), ("Jan 24 2025", "2025-01-24"), ("soon", None),
])
def test_parse_date(s, want):
    assert parse_date(s) == want


def test_normalize_text_strips_accents_articles_punctuation():
    assert normalize_text("  The Café, Ltd. ") == "cafe ltd"
    assert normalize_text("Smith & Sons") == normalize_text("smith and sons")


def test_number_key_accepts_formats_and_rejects_neighbours():
    key = Answer(canonical="3,000", type="number", variants=["three thousand"])
    assert grade("3000", key).outcome == CORRECT
    assert grade("three thousand", key).outcome == CORRECT
    assert grade("The benchmark had 3,000 questions.", key).outcome == CORRECT
    assert grade("2,700", key).outcome == INCORRECT


def test_relative_tolerance():
    key = Answer(canonical="100", type="number", rel_tol=0.05)
    assert grade("104", key).outcome == CORRECT
    assert grade("106", key).outcome == INCORRECT


def test_date_and_text_keys():
    assert grade("24 Jan 2025", Answer("2025-01-24", type="date")).outcome == CORRECT
    assert grade("the University of Pennsylvania", Answer("University of Pennsylvania")).outcome == CORRECT
    assert grade("Penn State", Answer("University of Pennsylvania", variants=["UPenn"])).outcome == INCORRECT


@pytest.mark.parametrize("ans", ["", "I don't know", "Unable to determine from sources", "could not find it"])
def test_abstentions_are_not_attempted(ans):
    assert grade(ans, Answer("3,000", type="number")).outcome == NOT_ATTEMPTED
