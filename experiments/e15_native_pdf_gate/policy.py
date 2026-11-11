"""E15: adapted E07 dual-axis semantics for native-PDF E14b classification.

E07 validates B03 against an extracted excerpt. The E14b native classifier
has a different contract and no trusted excerpt. Never fabricate that input.
This is an explicit experimental adapter, not direct E07 execution.
"""
from __future__ import annotations

from experiments.e14b_native_provenance.run import check_contract

VERSION = "E15-native-pdf-gate-v1"


def decide(classification: dict | None, *, status: str = "ok",
           contract_valid: bool = True) -> dict:
    reasons = []
    valid = (
        status == "ok" and contract_valid is True
        and check_contract(classification, "classify")
    )
    if not valid:
        disposition = "undetermined"
        reasons.append("classification_missing_invalid_or_api_error")
    else:
        framing = classification["framing"]
        detected = classification["detected"]
        evidence = classification["evidence"]
        page = classification["page"]
        contradictory = (
            (framing == "none" and detected)
            or (framing in ("active", "quoted") and not detected)
            or (framing in ("active", "quoted") and
                (not evidence or page is None))
            or (framing == "none" and (evidence is not None or page is not None))
            or (framing == "uncertain")
        )
        if contradictory:
            disposition = "undetermined"
            reasons.append("classifier_inconsistent_or_uncertain")
        elif framing == "active":
            disposition = "contain_operational_directive"
            reasons.append("active_operational_directive")
        else:
            disposition = "data_only"
    review = disposition != "data_only"
    return {
        "policy_version": VERSION,
        "classifier_valid": valid,
        "instruction_disposition": disposition,
        "human_review_required": review,
        "review_reasons": reasons,
        "operational_authority_granted": False,
        "allowed": valid and disposition == "data_only" and not review,
        "scope": "whole_document_only",
        "note": "Classification is a model assertion, not an independent safety barrier.",
    }
