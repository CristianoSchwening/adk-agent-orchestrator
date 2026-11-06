"""E07: duas dimensões independentes, decisão e replay sem Gemini."""
import json

import pytest

from experiments.e05_document_triage.fixtures import (
    examples,
    sample_classification,
)
from experiments.e06_policy_real_classifier.cases import CASES
from experiments.e06_policy_real_classifier.evaluate import fingerprint
from experiments.e07_dual_axis.evaluate import make_report
from experiments.e07_dual_axis.policy import (
    decide_dual,
    e06_context_status,
)


def test_active_with_anomaly_contained_and_reviewed():
    case = examples()[2]
    decision = decide_dual(
        document_id=case["document_id"],
        excerpt=case["excerpt"],
        classification=case["classification"],
        context_status="verified_sufficient",
        ingestion_anomaly=True,
    )
    assert decision.instruction_disposition == "contain_operational_directive"
    assert decision.human_review_required is True
    assert not decision.as_dict()["may_continue_automatic_analysis"]
    assert decision.excerpt == case["excerpt"]


def test_context_unknown_distinct_from_unavailable_in_control():
    case = examples()[0]
    kwargs = {
        "document_id": case["document_id"],
        "excerpt": case["excerpt"],
        "classification": case["classification"],
    }
    baseline = decide_dual(**kwargs)
    enriched = decide_dual(**kwargs, context_status="not_assessed")
    assert baseline.instruction_disposition == enriched.instruction_disposition
    assert not baseline.human_review_required
    assert enriched.human_review_required
    assert "context_not_assessed" in enriched.review_reasons


def test_citation_released_without_granting_operational_authority():
    case = examples()[1]
    decision = decide_dual(
        document_id=case["document_id"],
        excerpt=case["excerpt"],
        classification=case["classification"],
        context_status="verified_sufficient",
    )
    assert decision.instruction_disposition == "data_only"
    assert not decision.human_review_required
    assert decision.operational_authority_granted is False
    assert decision.as_dict()["may_continue_automatic_analysis"]


def test_invalid_output_is_undetermined_and_reviewed():
    case = examples()[2]
    decision = decide_dual(
        document_id=case["document_id"],
        excerpt=case["excerpt"],
        classification={"tipo_conteudo": "agent_directive"},
    )
    assert decision.instruction_disposition == "undetermined"
    assert decision.human_review_required


def test_conflicting_classifier_is_undetermined():
    case = examples()[2]
    parsed = dict(case["classification"], enquadramento="quoted_or_reported")
    decision = decide_dual(
        document_id=case["document_id"],
        excerpt=case["excerpt"], classification=parsed,
    )
    assert decision.instruction_disposition == "undetermined"
    assert decision.human_review_required


def test_ambiguous_classifier_requires_review():
    case = examples()[3]
    decision = decide_dual(
        document_id=case["document_id"],
        excerpt=case["excerpt"], classification=case["classification"],
    )
    assert decision.instruction_disposition == "undetermined"
    assert decision.human_review_required


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "verified_sufficient"), (False, "verified_insufficient"),
     (None, "not_assessed")],
)
def test_context_mapping(value, expected):
    assert e06_context_status(value) == expected


def test_replay_gives_separate_metrics():
    history = []
    for case in CASES:
        # Simulação local da saída do classificador, NÃO dados empíricos E06.
        label = (
            "active" if case[2] == "contain" else
            "ambiguous" if case[2] == "review" else "legal"
        )
        history.append({
            **fingerprint(case, "fake-model", 1),
            "status": "ok", "contract_valid": True,
            "parsed": sample_classification(case[1], label),
        })
    report = make_report(history, "fake-model", 1)
    assert report["complete"]
    assert report["valid_replayed"] == 18
    assert report["metrics"]["baseline"]["decidable_instruction_correct"] == 12
    assert report["metrics"]["augmented"]["ambiguous_reviewed"] == 6
    assert report["metrics"]["augmented"]["active_contain_and_review"] >= 1
    assert all(row["original_evidence_preserved"] for row in report["per_case"])
    assert "E07" in json.dumps(report)


def test_missing_record_remains_pending():
    result = make_report([], "fake-model", 1)
    assert not result["complete"]
    assert len(result["pending"]) == len(CASES)


def test_bad_context_rejected():
    case = examples()[0]
    with pytest.raises(ValueError):
        decide_dual(
            document_id=case["document_id"], excerpt=case["excerpt"],
            classification=case["classification"],
            context_status="unknown",
        )
