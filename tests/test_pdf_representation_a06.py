"""A06: texto OCR invisível legítimo dispara o mesmo sinal estrutural do A01."""
from __future__ import annotations

import fitz

from experiments.pdf_representation.a06_ocr import LINES, create_pair, report_pair


def test_a06_image_only_and_searchable_ocr(tmp_path):
    clean, ocr = create_pair(tmp_path)
    with fitz.open(clean) as before, fitz.open(ocr) as after:
        assert before[0].get_pixmap(alpha=False).samples == after[0].get_pixmap(
            alpha=False
        ).samples
        assert not before[0].get_text("text").strip()
        assert all(line in after[0].get_text("text") for line in LINES)
        assert all(span["type"] == 3 for span in after[0].get_texttrace())


def test_a06_diagnostic_is_benign_despite_hidden_spans(tmp_path):
    result = report_pair(tmp_path)
    assert result["classification_ground_truth"] == "benign_searchable_ocr"
    assert result["visual_parity"]
    assert result["extraction_difference"]
    assert result["hidden_spans_flagged_by_a01"] == len(LINES)
    assert result["scan_without_ocr_extracts_empty_text"]
    assert result["ocr_recovers_all_lines"]
