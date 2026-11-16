"""E24 offline tests; never call Gemini or legal ADK."""
from copy import deepcopy

import pytest

from experiments.e24_semantic_boundaries.generate import (
    ORDER,
    PAIRS,
    SPECS,
    generate,
)
from experiments.e24_semantic_boundaries.run import (
    fingerprint,
    reviewer_sheet,
    summarize,
)


def _answer(framing: str) -> dict:
    is_directive = framing != "none"
    return {
        "status": "ok",
        "contract_valid": True,
        "parsed": {
            "detected": is_directive,
            "recipient": "agent" if is_directive else "none",
            "framing": framing,
            "redirects_analyst": framing == "active",
            "evidence": "evidence" if is_directive else None,
            "page": 1 if is_directive else None,
            "notes": "synthetic",
        },
        "usage": {"total_token_count": 950},
    }


def test_corpus_balanced_with_six_contrast_pairs():
    assert len(ORDER) == 12
    assert len(PAIRS) == 6
    for pair in PAIRS:
        labels = [
            spec["truth"] for spec in SPECS.values() if spec["pair"] == pair
        ]
        assert len(labels) == 2
        assert "active" in labels
        assert any(label in {"none", "quoted"} for label in labels)


def test_generate_native_pdfs_and_fingerprints(tmp_path):
    cases = generate(tmp_path)
    assert len(cases) == 12
    for cid, case in cases.items():
        assert (tmp_path / f"E24_{cid}.pdf").exists()
        a = fingerprint(case, cid, "original", "fake")
        b = fingerprint(case, cid, "structured", "fake")
        for key in ("pdf_sha256", "system_sha256", "prompt_sha256"):
            assert a[key] == b[key]
        assert a["schema_sha256"] is None
        assert isinstance(b["schema_sha256"], str)


def test_reviewer_sheet_hides_labels_and_model_outputs(tmp_path):
    cases = generate(tmp_path)
    sheet = reviewer_sheet(cases)
    assert sheet["cases"]
    for item in sheet["cases"]:
        assert item["label"] is None
        assert "truth" not in item
        assert "pair" not in item
        assert "observation" not in item


def test_semantic_regression_detected_with_structural_validity(tmp_path):
    cases = generate(tmp_path)
    original = _answer("none")
    structured = _answer("active")
    history = {
        ("C111", "original"): original,
        ("C111", "structured"): structured,
    }
    before = deepcopy(history)
    result = summarize(cases, history, ["C111"], "fake")
    assert result["paired_comparisons"][0]["decision_changed"] is True
    assert result["metrics_by_arm"]["structured"]["provisional_false_blocks"] == 1
    assert history == before


def test_invalid_list_cannot_be_authorized(tmp_path):
    cases = generate(tmp_path)
    invalid = _answer("none")
    invalid["parsed"] = [invalid["parsed"]]
    invalid["contract_valid"] = False
    result = summarize(cases, {("C111", "original"): invalid}, ["C111"], "fake")
    row = result["rows"][0]
    assert row["authorized"] is None
    assert not row["contract_valid"]


def test_review_labels_not_marked_adjudicated(tmp_path):
    cases = generate(tmp_path)
    result = summarize(cases, {}, list(ORDER), "fake")
    assert result["independent_review_required"]
    assert all(not row["provisional_label_reviewed"] for row in result["rows"])
