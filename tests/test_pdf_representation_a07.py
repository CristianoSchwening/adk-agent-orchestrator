"""Testes offline do A07: sem API, OCR externo ou arquivos de usuário."""
from experiments.pdf_representation.a07_correspondence import (
    EXTRA_LINE, OCR_ALTERED, compare_lines, run,
)


def test_exact_match():
    assert compare_lines(["ABC"], ["ABC"])["exact_match"]


def test_added_line():
    result = compare_lines(["ABC"], ["ABC", "EXTRA"])
    assert result["observations"][0]["kind"] == "additional_extracted_text"


def test_character_substitution():
    result = compare_lines(["FEV-2026"], ["FEV-2O26"])
    assert result["observations"][0]["kind"] == "line_substitution"
    assert result["observations"][0]["similarity"] > 0.8


def test_three_pdf_conditions(tmp_path):
    report = run(tmp_path)
    assert report["visual_parity_all_three"]
    control, extra, typo = report["conditions"]
    assert control["exact_match"] and control["invisible_span_count"] == 6
    assert extra["invisible_span_count"] == 7
    assert extra["observations"][0]["kind"] == "additional_extracted_text"
    assert extra["observations"][0]["extracted"] == [EXTRA_LINE]
    assert typo["invisible_span_count"] == 6
    assert typo["observations"][0]["kind"] == "line_substitution"
    assert typo["observations"][0]["extracted"] == [OCR_ALTERED]
