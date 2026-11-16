"""E23 local tests; no Gemini, no downstream ADK."""
import json
from copy import deepcopy

import pytest

from experiments.e23_structured_output.run import (
    ARMS,
    CONTESTED,
    RecipientClassification,
    _load,
    classify_structured,
    fingerprint,
    historic_replay,
    summarize,
)
from experiments.e21_tcu_indirect.generate import ORDER, generate


def record(framing="active", redirected=True, status="ok", contract=True):
    detected = framing in ("active", "quoted")
    return {
        "status": status,
        "contract_valid": contract,
        "parsed": {
            "detected": detected,
            "recipient": "agent" if detected else "none",
            "framing": framing,
            "redirects_analyst": redirected,
            "evidence": "texto" if detected else None,
            "page": 1 if detected else None,
            "notes": "teste",
        },
        "usage": {"total_token_count": 700},
    }


def test_structured_model_is_strict():
    valid = record()["parsed"]
    assert RecipientClassification.model_validate(valid).framing == "active"
    with pytest.raises(Exception):
        RecipientClassification.model_validate({**valid, "extra": "x"})
    with pytest.raises(Exception):
        RecipientClassification.model_validate({**valid, "page": 0})


def test_arms_use_same_prompt_and_pdf_but_distinct_schema_fingerprint(tmp_path):
    cases = generate(tmp_path)
    case = cases["priority_override_attack"]
    a = fingerprint(case, "priority_override_attack", "original", "fake")
    b = fingerprint(case, "priority_override_attack", "structured", "fake")
    for field in ["pdf_sha256", "system_sha256", "prompt_sha256"]:
        assert a[field] == b[field]
    assert a["schema_sha256"] is None
    assert isinstance(b["schema_sha256"], str) and len(b["schema_sha256"]) == 64


def test_live_summary_does_not_normalize_invalid_list(tmp_path):
    cases = generate(tmp_path)
    cid = "priority_override_attack"
    invalid = record()
    invalid["parsed"] = [invalid["parsed"]]
    invalid["contract_valid"] = False
    summary = summarize(cases, {(cid, "structured"): invalid}, [cid], "fake", None)
    row = next(x for x in summary["new_observations"]
               if x["arm"] == "structured")
    assert not row["contract_valid"]
    assert row["authorized"] is None
    assert not summary["complete_new_calls"]


def test_adjudication_flag_and_gate_unchanged(tmp_path):
    cases = generate(tmp_path)
    cid = "source_omission_control"
    left = record("none", redirected=False)
    right = record("active", redirected=True)
    inputs = {(cid, "original"): left, (cid, "structured"): right}
    untouched = deepcopy(inputs)
    summary = summarize(cases, inputs, [cid], "fake", None)
    assert summary["ground_truth_contested_cases"] == list(CONTESTED)
    assert summary["paired_comparisons"][0]["authorization_changed"]
    assert inputs == untouched


def test_history_replay_is_not_new_call():
    attempts = {
        (cid, arm): []
        for cid in ORDER
        for arm in ("control", "recipient_aware")
    }
    cid = "priority_override_attack"
    invalid_list = record()
    invalid_list["contract_valid"] = False
    invalid_list["parsed"] = [invalid_list["parsed"]]
    attempts[(cid, "recipient_aware")].append(invalid_list)
    replay = historic_replay(attempts)
    assert replay["candidate_recovered_cases"] == 1
    assert replay["not_new_model_calls"]


def test_fingerprint_rejects_mismatch(tmp_path):
    cases = generate(tmp_path / "pdf")
    path = tmp_path / "history.jsonl"
    path.write_text(
        json.dumps({
            "experiment": "E23",
            "case_id": "source_omission_attack",
            "arm": ARMS[0],
        }) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fingerprint"):
        _load(path, cases, "fake")
