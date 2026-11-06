"""E05: testes determinísticos da política, não testes empíricos de LLM."""
import json

import pytest

from experiments.e05_document_triage.fixtures import (
    examples,
    sample_classification,
)
from experiments.e05_document_triage.policy import decide, result_for_downstream


@pytest.mark.parametrize(
    ("index", "expected"),
    [(0, "release"), (1, "release"), (2, "contain"), (3, "review")],
)
def test_triage_categories(index, expected):
    decision = decide(**examples()[index])
    assert decision.action == expected
    assert decision.operational_authority_granted is False
    assert decision.evidence_excerpt == examples()[index]["excerpt"]


def test_ambiguity_never_silently_released():
    case = examples()[3]
    decision = decide(**case)
    assert decision.action == "review"
    assert "model_uncertainty_or_review" in decision.reasons


def test_external_context_incomplete_overrides_confident_release():
    case = examples()[0]
    decision = decide(**{**case, "context_complete": False})
    assert decision.action == "review"
    assert "insufficient_document_context" in decision.reasons


def test_ingestion_anomaly_requires_review_without_claiming_attack():
    case = examples()[1]
    decision = decide(**{**case, "ingestion_anomaly": True})
    assert decision.action == "review"
    assert "ingestion_representation_anomaly" in decision.reasons


def test_invalid_output_requires_review_preserving_original():
    case = examples()[2]
    text = case["excerpt"]
    decision = decide(
        document_id=case["document_id"],
        excerpt=text, classification={"tipo_conteudo": "agent_directive"}
    )
    assert decision.action == "review"
    assert decision.classification is None
    assert decision.evidence_excerpt == text


def test_conflicting_classification_requires_review():
    case = examples()[2]
    parsed = dict(case["classification"], enquadramento="quoted_or_reported")
    decision = decide(**{**case, "classification": parsed})
    assert decision.action == "review"
    assert "classifier_inconsistency" in decision.reasons


def test_contain_is_not_destructive_redaction():
    case = examples()[2]
    decision = decide(**case)
    output = result_for_downstream(decision)
    assert output["triage_action"] == "contain"
    assert not output["may_continue_automatic_analysis"]
    assert output["evidence_text"] == case["excerpt"]
    assert output["operational_authority"] == "denied"
    assert len(output["evidence_sha256"]) == 64


def test_context_unknown_does_not_invent_ambiguity():
    case = examples()[0]
    decision = decide(**{**case, "context_complete": None})
    assert decision.action == "release"


def test_classification_evidence_must_match_literal_excerpt():
    case = examples()[0]
    parsed = dict(case["classification"], evidencia_textual="texto inventado")
    decision = decide(**{**case, "classification": parsed})
    assert decision.action == "review"


def test_fixture_is_json_serializable():
    decisions = [decide(**c).as_dict() for c in examples()]
    assert len(json.dumps(decisions, ensure_ascii=False)) > 100


def test_invalid_inputs_fail_explicitly():
    case = examples()[0]
    with pytest.raises(ValueError):
        decide(**{**case, "excerpt": ""})


def test_sample_classification_rejects_unknown_label():
    with pytest.raises(ValueError):
        sample_classification("texto", "other")
