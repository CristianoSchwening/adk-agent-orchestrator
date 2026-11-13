"""E20: offline operational triage on frozen E15/E18 model responses.

No triage state grants authority. 'review' means NO automatic ADK invocation.
"""
from __future__ import annotations

from experiments.e15_native_pdf_gate.policy import decide as decide_e15
from experiments.e18_recipient_aware.run import new_decision, check_new

VERSION = "E20-triage-v1"


def triage(record: dict | None, arm: str) -> dict:
    if arm not in ("control", "recipient_aware"):
        raise ValueError("Unknown arm")
    if record is None or record.get("status") != "ok" or record.get("contract_valid") is not True:
        return _result("technical_hold", "missing_invalid_or_api_error")
    obj = record.get("parsed")
    if arm == "control":
        original = decide_e15(obj, status="ok", contract_valid=True)
        if not original["classifier_valid"]:
            return _result("technical_hold", "invalid_classifier_contract")
        if original["allowed"]:
            return _result("allow", "data_only")
        if original["instruction_disposition"] == "contain_operational_directive":
            return _result("contain", "active_operational_directive")
        return _result("review", "classifier_uncertain_or_inconsistent")
    if not check_new(obj):
        return _result("technical_hold", "invalid_classifier_contract")
    original = new_decision(obj)
    if original["allowed"]:
        return _result("allow", "data_only")
    if original["reason"] == "active_redirect":
        return _result("contain", "active_redirect")
    return _result("review", original["reason"])


def _result(disposition: str, reason: str) -> dict:
    if disposition not in {"allow", "contain", "review", "technical_hold"}:
        raise ValueError("Invalid disposition")
    return {
        "policy_version": VERSION,
        "disposition": disposition,
        "reason": reason,
        "automatic_agent_authorized": disposition == "allow",
        "requires_human_review": disposition == "review",
        "needs_technical_recovery": disposition == "technical_hold",
        "operational_authority_granted": False,
    }
