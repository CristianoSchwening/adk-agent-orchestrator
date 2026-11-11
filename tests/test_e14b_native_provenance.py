"""E14b: verificações sem chamadas à API."""
import json
from pathlib import Path

import pytest

from experiments.e14b_native_provenance.generate import generate
from experiments.e14b_native_provenance.run import (
    ARMS, PHASES, check_contract, evaluate, fingerprint, load_history,
    reference_text, report_for, source_matches,
)


def test_synthetic_fact_manifest_is_independent_of_prompt(tmp_path):
    cases = generate(tmp_path)
    assert len(cases) == 6
    assert cases["mixed_image"]["facts"][1]["amount"] == 370
    text = reference_text(Path(cases["mixed_image"]["path"]))
    assert "370" not in text
    assert "2860" not in text  # PDF usa formatação monetária pt-BR
    assert cases["hidden_white"]["framing"] == "active"


def test_schema_and_source_normalization():
    assert source_matches("P-258", "PETICAO FICTICIA P-258")
    assert not source_matches("P-258", "PETICAO FICTICIA P-2589")
    classification = {
        "detected": True, "framing": "active", "evidence": "trecho",
        "page": 1, "notes": "teste",
    }
    extraction = {
        "facts": [{
            "amount_brl": 2860, "source": "PETICAO P-258",
            "page": 1, "evidence": "trecho",
        }],
        "unverified_pages": [], "notes": "teste",
    }
    assert check_contract(classification, "classify")
    assert check_contract(extraction, "extract")
    assert not check_contract({"facts": []}, "extract")


def test_fact_to_source_page_and_evidence_metrics(tmp_path):
    case = generate(tmp_path)["mixed_image"]
    valid = {"status": "ok", "contract_valid": True, "parsed": {
        "facts": [{
            "amount_brl": 2860, "source": "PETICAO FICTICIA P-258",
            "page": 1, "evidence": case["facts"][0]["evidence"],
        }], "unverified_pages": [], "notes": "",
    }}
    report = evaluate(case, "extract", valid)
    assert report["matched_fact_count"] == 1
    assert report["missing_fact_indices"] == [1]
    assert report["evidence_exact_match_by_fact"] == [True, False]


def test_history_rejects_different_model(tmp_path):
    cases = generate(tmp_path)
    case = cases["hidden_white"]
    ref = reference_text(Path(case["path"]))
    row = {
        **fingerprint(case, "hidden_white", "model-a", "native_pdf", "classify", ref),
        "status": "ok", "parsed": None, "contract_valid": False,
    }
    file = tmp_path / "history.jsonl"
    file.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert load_history(file, cases, ["hidden_white"], "model-a")
    with pytest.raises(ValueError, match="fingerprint"):
        load_history(file, cases, ["hidden_white"], "model-b")


def test_report_does_not_claim_behavioral_security(tmp_path):
    cases = generate(tmp_path)
    report = report_for(cases, {}, ["hidden_white"], "model")
    assert not report["complete"]
    assert report["calls_expected"] == len(ARMS) * len(PHASES)
    assert report["valid_calls"] == 0
