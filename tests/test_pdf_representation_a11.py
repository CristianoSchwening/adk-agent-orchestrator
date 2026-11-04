"""A11: preservar documentação dos pontos cegos existentes no A10."""
from experiments.pdf_representation.a11_integrity import cases, evaluate


def test_matrix_contains_six_positive_and_control():
    items = cases()
    assert len(items) == 7
    assert sum(x["expected_discrepancy"] for x in items) == 6


def test_existing_a10_detects_amount_and_date():
    by_id = {r["case_id"]: r for r in evaluate()["cases"]}
    assert by_id["A11_AMOUNT_DIGIT"]["signal_present"]
    assert by_id["A11_DATE_DIGIT"]["signal_present"]


def test_existing_a10_does_not_alert_punctuation_collisions():
    by_id = {r["case_id"]: r for r in evaluate()["cases"]}
    assert by_id["A11_PUNCT_COLLISION"]["false_negative"]
    assert by_id["A11_CURRENCY_SYMBOL"]["false_negative"]


def test_existing_a10_does_not_alert_small_displacement():
    by_id = {r["case_id"]: r for r in evaluate()["cases"]}
    assert by_id["A11_NEAR_DISPLACEMENT"]["false_negative"]


def test_repeated_value_needs_review_and_control_does_not():
    by_id = {r["case_id"]: r for r in evaluate()["cases"]}
    assert by_id["A11_REPEATED_VALUE"]["signal_present"]
    assert not by_id["A11_REPEATED_CONTROL"]["signal_present"]
