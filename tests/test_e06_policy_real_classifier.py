"""E06: testes offline do corpus, histórico e avaliação emparelhada."""
import json

import pytest

from experiments.e05_document_triage.fixtures import sample_classification
from experiments.e06_policy_real_classifier import evaluate
from experiments.e06_policy_real_classifier.cases import CASES
from experiments.instructional_nature.b03 import INSTRUCTION, validate_output


def test_corpus_frozen_and_balanced():
    assert len(CASES) == len({row[0] for row in CASES}) == 18
    assert {
        action: sum(row[2] == action for row in CASES)
        for action in ("release", "contain", "review")
    } == {"release": 6, "contain": 6, "review": 6}
    assert sum(row[3] is False for row in CASES) >= 3
    assert sum(row[4] for row in CASES) >= 2
    assert all(row[1] and row[0].startswith("E06_") for row in CASES)


def example_prediction(case):
    expected = case[2]
    if expected == "release":
        label = "quoted" if "IA," in case[1] or "robô," in case[1] else "legal"
    elif expected == "contain":
        label = "active"
    else:
        label = "ambiguous"
    return sample_classification(case[1], label)


def test_fixture_output_has_frozen_schema():
    for case in CASES:
        parsed = example_prediction(case)
        assert validate_output(
            json.dumps(parsed, ensure_ascii=False), case[1]
        )["contract_valid"]
    assert "context_complete" not in INSTRUCTION


def test_no_metadata_and_metadata_arms_distinct():
    results = []
    for case in CASES:
        row = {"parsed": example_prediction(case), "repetition": 1}
        result = evaluate.assess_row(case, row)
        assert result["evidence_preserved"]
        results.append(result)
    m1 = evaluate.arm_metrics(results, "policy_without_metadata")
    m2 = evaluate.arm_metrics(results, "policy_with_metadata")
    assert m1["evaluated"] == m2["evaluated"] == 18
    assert m1["unsafe_release_of_active"] == 0
    assert m2["ambiguous_not_reviewed"] == 0
    assert m2["legitimate_sent_to_review"] >= m1["legitimate_sent_to_review"]


def test_metadata_not_used_in_classifier_prompt():
    from experiments.instructional_nature.b03 import build_prompt

    for case in CASES:
        prompt = build_prompt(case[0], case[1])
        assert "context_complete" not in prompt
        assert "ingestion_anomaly" not in prompt
        assert "expected_action" not in prompt


def test_report_valid_and_pending():
    model = "fake-model"
    history = [
        {
            **evaluate.fingerprint(case, model, 1),
            "status": "ok", "contract_valid": True,
            "parsed": example_prediction(case),
        }
        for case in CASES
    ]
    selected = evaluate.select_history(history, model, 1)
    result = evaluate.report(selected, history, model, 1)
    assert result["complete"]
    assert result["valid_responses"] == 18
    assert len(result["paired_comparison"]) == 18
    assert not result["pending"]
    assert len(result["instruction_sha256"]) == 64
    assert len(result["corpus_sha256"]) == 64


def test_no_oracle_labels_in_fingerprint_or_prompt():
    for case in CASES:
        serialized = json.dumps(evaluate.fingerprint(case, "model", 1))
        assert "expected_action" not in serialized
        assert case[2] not in serialized


def test_incompatible_history_model_and_corpus_rejected():
    case = CASES[0]
    row = {
        **evaluate.fingerprint(case, "m1", 1),
        "status": "ok", "contract_valid": True,
        "parsed": example_prediction(case),
    }
    with pytest.raises(ValueError, match="incompatível"):
        evaluate.select_history([row], "m2", 1)
    with pytest.raises(ValueError, match="incompatível"):
        evaluate.select_history([{**row, "corpus_sha256": "bad"}], "m1", 1)


def test_invalid_json_not_counted_as_semantic_error():
    case = CASES[0]
    row = {
        **evaluate.fingerprint(case, "m1", 1),
        "status": "ok", "contract_valid": False, "parsed": None,
    }
    latest = evaluate.select_history([row], "m1", 1)
    result = evaluate.report(latest, [row], "m1", 1)
    assert result["valid_responses"] == 0
    assert result["historical_invalid_contracts"] == 1
    assert len(result["pending"]) == 18
