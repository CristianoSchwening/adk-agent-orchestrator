"""E18 offline tests, with no Gemini calls."""
from experiments.e18_recipient_aware.generate import ORDER, generate
from experiments.e18_recipient_aware.run import (
    check_new, fingerprint, new_decision, report,
)


def model_output(framing, recipient="none"):
    return {
        "detected": framing in ("active", "quoted"),
        "recipient": recipient, "framing": framing,
        "redirects_analyst": framing == "active",
        "evidence": "Instrucao citada" if framing in ("active", "quoted") else None,
        "page": 1 if framing in ("active", "quoted") else None,
        "notes": "teste",
    }


def test_recipient_gate_preserves_legitimate_instructions():
    assert new_decision(model_output("none", "professional"))["allowed"]
    assert new_decision(model_output("none", "court"))["allowed"]
    assert new_decision(model_output("quoted", "agent"))["allowed"]
    assert not new_decision(model_output("active", "agent"))["allowed"]
    assert not new_decision(model_output("active", "court"))["allowed"]
    assert not new_decision(model_output("uncertain"))["allowed"]
    assert not new_decision(None, "error", False)["allowed"]


def test_contract_and_consistency():
    assert check_new(model_output("none"))
    assert not check_new({"framing": "none"})
    broken = model_output("active", "agent")
    broken["redirects_analyst"] = False
    assert not new_decision(broken)["allowed"]


def test_holdout_and_incomplete_report(tmp_path):
    cases = generate(tmp_path)
    assert len(cases) == 8
    assert "editorial_note" not in cases
    assert len(set(fingerprint(c, cid, "control", "fake")["pdf_sha256"]
                   for cid, c in cases.items())) == 8
    result = report(cases, {}, list(ORDER), "fake")
    assert not result["complete"]
    assert len(result["pending"]) == 16
    assert result["valid_calls"] == 0
