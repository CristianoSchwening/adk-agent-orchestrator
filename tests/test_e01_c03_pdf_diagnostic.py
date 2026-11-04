"""Validacao offline do diagnostico C03."""
from experiments.e01_prompt_injection.c03_pdf_diagnostic import MARKER, prepare_pair


def test_c03_render_vs_text(tmp_path):
    report = prepare_pair(tmp_path)
    assert report["render_identical"]
    assert report["marker_in_marked"]
    assert not report["marker_in_control"]
    assert report["evidence_preserved"]
    assert MARKER in report["marked_extracted_text"]
