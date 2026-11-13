"""E19: repeatability metrics and fail-closed completion without API."""
import json

import pytest

from experiments.e18_recipient_aware.generate import generate
from experiments.e19_classifier_stability.run import (
    fingerprint, load, report,
)


def row(arm, framing, *, allowed=True):
    if arm == "control":
        result = {
            "detected": framing in ("active", "quoted"),
            "framing": framing,
            "evidence": "Mensagem" if framing in ("active", "quoted") else None,
            "page": 1 if framing in ("active", "quoted") else None,
            "notes": "exemplo",
        }
    else:
        result = {
            "detected": framing in ("active", "quoted"),
            "recipient": "agent" if framing in ("active", "quoted") else "other",
            "framing": framing,
            "redirects_analyst": framing == "active",
            "evidence": "Mensagem" if framing in ("active", "quoted") else None,
            "page": 1 if framing in ("active", "quoted") else None,
            "notes": "exemplo",
        }
    return {"status": "ok", "contract_valid": True,
            "parsed": result, "usage": {"total_token_count": 100}}


def test_repetitions_detect_flip(tmp_path):
    cases = generate(tmp_path)
    history = {
        ("raster_citation", "control", 1): row("control", "quoted"),
        ("raster_citation", "control", 2): row("control", "active"),
        ("raster_citation", "recipient_aware", 1): row("recipient_aware", "quoted"),
        ("raster_citation", "recipient_aware", 2): row("recipient_aware", "quoted"),
    }
    result = report(cases, history, ["raster_citation"], 2, "fake")
    assert result["complete"]
    group = {g["arm"]: g for g in result["stability_by_case_arm"]}
    assert not group["control"]["authorization_stable"]
    assert group["recipient_aware"]["authorization_stable"]
    assert result["metrics_by_arm"]["control"]["unnecessary_blocks"] == 1
    assert result["metrics_by_arm"]["recipient_aware"]["token_total_observed"] == 200


def test_errors_are_pending(tmp_path):
    cases = generate(tmp_path)
    history = {("registry_instruction", "control", 1): {
        "status": "error", "contract_valid": False, "parsed": None,
    }}
    result = report(cases, history, ["registry_instruction"], 2, "fake")
    assert not result["complete"]
    assert len(result["pending"]) == 4


def test_rejects_different_pdf_fingerprint(tmp_path):
    cases = generate(tmp_path / "pdf")
    path = tmp_path / "history.jsonl"
    row_data = {
        **fingerprint(cases["registry_instruction"],
                      "registry_instruction", "control", 1, "fake"),
        "pdf_sha256": "different",
    }
    path.write_text(json.dumps(row_data) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        load(path, cases, "fake")
