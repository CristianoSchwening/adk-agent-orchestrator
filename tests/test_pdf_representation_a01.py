"""Testes de A01: fixture local sem chamadas a modelos ou dados reais."""

from __future__ import annotations

import fitz

from experiments.pdf_representation.analyze import build_report


def _make_pdf(path, *, marker: bool):
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        for idx, text in enumerate((
            "JAN-2026: R$ 2.000,00", "FEV-2026: R$ 2.000,00",
            "MAR-2026: R$ 2.000,00", "TOTAL: R$ 6.000,00",
        )):
            page.insert_text((50, 80 + idx * 30), text)
        if marker:
            page.insert_text((50, 270), "MARCADOR A01 BENIGNO", render_mode=3)
        doc.save(path)


def test_a01_hidden_marker_is_flagged_and_render_equal(tmp_path):
    clean, flagged = tmp_path / "controle.pdf", tmp_path / "marcador.pdf"
    _make_pdf(clean, marker=False)
    _make_pdf(flagged, marker=True)
    report = build_report(clean, flagged)
    result = report["comparison"]
    assert result["visual_parity"]
    assert result["extraction_difference"]
    assert result["legitimate_content_preserved"]
    assert result["candidate_flagged_spans"] >= 1
    assert any(
        "MARCADOR" in span["text"]
        for page in report["candidate"]["pages"]
        for span in page["flagged_spans"]
    )
    assert all(not page["flagged_spans"] for page in report["control"]["pages"])


def test_a01_identical_control(tmp_path):
    clean = tmp_path / "controle.pdf"
    _make_pdf(clean, marker=False)
    report = build_report(clean, clean)
    assert report["comparison"]["visual_parity"]
    assert not report["comparison"]["extraction_difference"]
    assert report["comparison"]["legitimate_content_preserved"]
