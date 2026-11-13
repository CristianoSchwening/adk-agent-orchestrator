"""E22 conservative offline adapter for one-element JSON arrays.

Do not overwrite original model output, change classifier prompts, or
authorize a sample before the original E18 semantic gate validates it.
"""
from __future__ import annotations

from experiments.e18_recipient_aware.run import check_new, new_decision, valid

VERSION = "E22-singleton-list-adapter-v1"


def normalize(record: dict | None, arm: str) -> dict:
    """Return a new diagnostic object; leave record untouched.

    For E15, never interpret the E18 schema or modify the response.
    For E18, only lift an exactly one-element list containing a
    structurally valid E18 object. Semantic contradictions still block.
    """
    if arm not in {"control", "recipient_aware"}:
        raise ValueError("Unrecognized arm")
    if record is None or record.get("status") != "ok":
        return _out("not_normalized", "missing_or_api_error", None)
    if valid(record):
        return _out("original_valid", "unchanged", record.get("parsed"))
    if arm != "recipient_aware":
        return _out("not_normalized", "control_arm_not_adapted", None)
    parsed = record.get("parsed")
    if type(parsed) is not list:
        return _out("not_normalized", "not_a_list", None)
    if len(parsed) != 1:
        return _out("not_normalized", "not_singleton", None)
    obj = parsed[0]
    if not check_new(obj):
        return _out("not_normalized", "invalid_inner_contract", None)
    gate = new_decision(obj, status="ok", contract_valid=True)
    return _out("recovered", "singleton_inner_contract_valid", obj, gate)


def _out(status: str, reason: str, parsed: dict | None,
         gate: dict | None = None) -> dict:
    return {
        "adapter_version": VERSION,
        "status": status,
        "reason": reason,
        "parsed": parsed,
        "semantic_gate": gate,
        "automatic_agent_authorized": (
            gate["allowed"] if status == "recovered" else None
        ),
    }
