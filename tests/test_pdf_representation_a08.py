"""Testes offline A08, sem Gemini e sem executar OCR nos testes unitários."""
from pathlib import Path

from experiments.pdf_representation.a08_independent_ocr import (
    compare_ocr_to_extracted,
)


def test_control_all_lines_matched():
    result = compare_ocr_to_extracted(["JAN-2026", "FEV-2026"], ["JAN-2026", "FEV-2026"])
    assert result["matched_count"] == 2
    assert not result["unmatched_extracted"]
    assert not result["approximate_matches"]


def test_additional_line_detected():
    result = compare_ocr_to_extracted(
        ["JAN-2026", "FEV-2026"], ["JAN-2026", "FEV-2026", "MARCADOR ADICIONAL"]
    )
    assert len(result["unmatched_extracted"]) == 1
    assert result["unmatched_extracted"][0]["text"] == "MARCADOR ADICIONAL"


def test_simulated_ocr_typo_is_not_silenced():
    result = compare_ocr_to_extracted(
        ["FEV-2026 | R$ 2.000,00"], ["FEV-2O26 | R$ 2.000,00"]
    )
    assert result["matched_count"] == 1
    assert len(result["approximate_matches"]) == 1
    assert result["approximate_matches"][0]["requires_review"]


def test_missing_line_is_recorded():
    result = compare_ocr_to_extracted(
        ["JAN-2026", "FEV-2026"], ["JAN-2026"]
    )
    assert len(result["unmatched_ocr"]) == 1
