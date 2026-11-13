"""E20 isolated policy and replay tests; never call Gemini."""
import pytest

from experiments.e20_policy_triage.policy import triage
from experiments.e20_policy_triage.run import analyze


def response(framing, redirects=False, recipient="agent"):
    return {
        "status": "ok", "contract_valid": True,
        "parsed": {
            "detected": framing in ("active", "quoted"),
            "recipient": recipient,
            "framing": framing,
            "redirects_analyst": redirects,
            "evidence": "frase" if framing in ("active", "quoted") else None,
            "page": 1 if framing in ("active", "quoted") else None,
            "notes": "teste",
        },
    }


def test_triad_and_no_automatic_authorization_on_conflict():
    assert triage(response("none", recipient="professional"), "recipient_aware")["disposition"] == "allow"
    assert triage(response("active", redirects=True), "recipient_aware")["disposition"] == "contain"
    inconsistent = triage(response("quoted", redirects=True), "recipient_aware")
    assert inconsistent["disposition"] == "review"
    assert not inconsistent["automatic_agent_authorized"]
    assert inconsistent["requires_human_review"]
    assert triage({"status": "error", "contract_valid": False}, "recipient_aware")["disposition"] == "technical_hold"


def test_control_policy_reused():
    control = {
        "status": "ok", "contract_valid": True,
        "parsed": {"detected": True, "framing": "active", "page": 1,
                   "evidence": "ataque", "notes": "teste"},
    }
    assert triage(control, "control")["disposition"] == "contain"
    assert triage(None, "control")["disposition"] == "technical_hold"


def test_replay_separates_human_review_from_attack_containment():
    history = {
        ("raster_citation", "recipient_aware", 0): {
            **response("quoted", redirects=True),
            "pdf_sha256": "a" * 64,
        },
        ("registry_instruction", "recipient_aware", 0): {
            **response("none", recipient="professional"),
            "pdf_sha256": "b" * 64,
        },
    }
    result = analyze({"E18": history}, model="fake")
    metrics = result["metrics_by_source_and_arm"]["E18"]["recipient_aware"]
    assert metrics["review"] == 1
    assert metrics["false_containment_of_legitimate"] == 0
    assert metrics["legitimate_sent_to_review"] == 1
    assert metrics["automatic_allow"] == 1
    assert metrics["authorization_changed_vs_original"] == 0


def test_replay_rejects_cross_experiment_pdf_changes():
    source = {("registry_instruction", "control", 0): {
        "status": "error", "contract_valid": False, "pdf_sha256": "a"*64,
    }}
    other = {("registry_instruction", "control", 1): {
        "status": "error", "contract_valid": False, "pdf_sha256": "b"*64,
    }}
    with pytest.raises(ValueError, match="PDF hash mismatch"):
        analyze({"E18": source, "E19": other}, model="fake")
