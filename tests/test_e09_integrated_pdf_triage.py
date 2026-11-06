"""E09: invariantes de integração com Gemini simulado e extração REAL PyMuPDF."""
from __future__ import annotations

import json

import pytest

from experiments.e05_document_triage.fixtures import sample_classification
from experiments.e09_integrated_pdf_triage.run import (
    VARIANTS, build_cases, evaluate, fingerprint, select_history,
)


def fake_history(cases, model):
    records = []
    for variant in VARIANTS:
        case = cases[variant]
        if not case["excerpt"].strip():
            continue
        label = {
            "control": "legal",
            "hidden_active": "active",
            "visible_quoted": "quoted",
        }[variant]
        records.append({
            **fingerprint(case, model),
            "status": "ok", "contract_valid": True,
            "parsed": sample_classification(case["excerpt"], label),
        })
    return records


def test_pdf_pipeline_and_no_ocr(tmp_path):
    cases = build_cases(tmp_path, regenerate=True)
    assert len(cases) == 4
    assert cases["control"]["diagnostic"]["signals"] == []
    assert cases["hidden_active"]["diagnostic"]["signals"] == [
        "non_rendered_text_operation"
    ]
    assert cases["image_only"]["excerpt"] == ""
    assert cases["image_only"]["diagnostic"]["signals"] == [
        "image_only_without_extracted_text"
    ]
    assert (
        cases["control"]["diagnostic"]["pages"][0]["render_sha256"]
        == cases["hidden_active"]["diagnostic"]["pages"][0]["render_sha256"]
    )


def test_valid_predictions_plus_real_ingestion_metadata(tmp_path):
    model = "fake-model"
    cases = build_cases(tmp_path, regenerate=True)
    history = fake_history(cases, model)
    selected = select_history(history, cases, model)
    report = evaluate(cases, selected, history, model)
    assert report["complete"]
    assert report["requested_classifier_calls"] == 3
    assert report["valid_classifier_responses"] == 3
    assert report["skipped_no_extractable_text"] == 1
    assert report["reference_comparisons"] == {"correct": 3, "evaluated": 3}
    by_variant = {x["variant"]: x for x in report["cases"]}
    assert by_variant["control"]["policy"]["may_continue_automatic_analysis"]
    assert by_variant["visible_quoted"]["policy"]["may_continue_automatic_analysis"]
    active = by_variant["hidden_active"]["policy"]
    assert active["instruction_disposition"] == "contain_operational_directive"
    assert active["human_review_required"]
    image = by_variant["image_only"]
    assert image["classifier_status"] == "skipped_no_extractable_text"
    assert image["classifier_prediction"] is None
    assert image["policy"]["instruction_disposition"] == "undetermined"
    assert image["policy"]["human_review_required"]
    assert all(x["pdf_sha256"] for x in report["cases"])
    assert "synthetic" not in report["mode"]
    assert json.loads(json.dumps(report))["complete"]


def test_missing_or_invalid_classifier_forces_review(tmp_path):
    cases = build_cases(tmp_path, regenerate=True)
    report = evaluate(cases, {}, [], "fake")
    assert not report["complete"]
    assert len(report["pending"]) == 3
    assert report["valid_classifier_responses"] == 0
    for row in report["cases"]:
        assert row["policy"]["human_review_required"]


def test_pdf_fingerprint_changes_rejected(tmp_path):
    model = "fake"
    cases = build_cases(tmp_path, regenerate=True)
    history = fake_history(cases, model)
    altered = dict(history[0], pdf_sha256="wrong")
    with pytest.raises(ValueError, match="fingerprint incompatível"):
        select_history([altered], cases, model)
