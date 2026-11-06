"""Testes E13 sem chamadas Gemini nem OCR."""
from experiments.e13_extraction_coverage.run import run


def test_all_expected_synthetic_mechanisms(tmp_path):
    result = run(tmp_path)
    assert all(result["checks"].values())
    assert len(result["cases"]) == 7
    assert result["known_synthetic_missing_facts"] == 2


def test_partial_extraction_is_not_declared_complete(tmp_path):
    result = run(tmp_path)
    cases = result["cases"]
    assert cases["raster_page"]["diagnostic"]["pages"][1]["extracted_text"] == ""
    assert "image_region_unassessed_without_ocr" in (
        cases["mixed_page"]["diagnostic"]["pages"][0]["signals"]
    )
    assert not cases["text_control"]["diagnostic"]["automatic_release"]


def test_two_axes_and_facts_not_deleted(tmp_path):
    result = run(tmp_path)
    cases = result["cases"]
    assert cases["opaque_overlay"]["diagnostic"]["security_representation_signals"]
    assert cases["vector_table"]["diagnostic"]["extraction_coverage_signals"]
    for case in cases.values():
        assert len(case["diagnostic"]["pdf_sha256"]) == 64
        assert not case["diagnostic"]["safe_for_legal_agent"]
