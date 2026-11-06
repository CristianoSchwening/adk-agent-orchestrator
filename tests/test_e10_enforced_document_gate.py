"""Gate E10: tests only, no Gemini calls."""
import asyncio

from experiments.e05_document_triage.fixtures import sample_classification
from experiments.e10_enforced_document_gate.run import (
    authorization,
    invoke_if_authorized,
)
from experiments.e09_integrated_pdf_triage.run import build_cases


def setup_cases(tmp_path):
    cases = build_cases(tmp_path, regenerate=True)
    records = {}
    for kind in ("control", "hidden_active", "visible_quoted"):
        case = cases[kind]
        label = {
            "control": "legal",
            "hidden_active": "active",
            "visible_quoted": "quoted",
        }[kind]
        records[case["case_id"]] = {
            "status": "ok", "contract_valid": True,
            "parsed": sample_classification(case["excerpt"], label),
        }
    return cases, records


def test_gate_blocks_active_and_unextractable(tmp_path):
    cases, records = setup_cases(tmp_path)
    decisions = authorization(cases, records)
    assert decisions["control"]["allowed"]
    assert decisions["visible_quoted"]["allowed"]
    assert not decisions["hidden_active"]["allowed"]
    assert decisions["hidden_active"]["review"]
    assert not decisions["image_only"]["allowed"]


def test_fail_closed_on_missing_classifier(tmp_path):
    cases, _ = setup_cases(tmp_path)
    decisions = authorization(cases, {})
    assert not any(item["allowed"] for item in decisions.values())


def test_rejection_never_invokes_runner(tmp_path):
    cases, records = setup_cases(tmp_path)
    decisions = authorization(cases, records)
    row = asyncio.run(
        invoke_if_authorized(
            None, cases["hidden_active"],
            decisions["hidden_active"]["allowed"],
        )
    )
    assert row["status"] == "blocked_by_gate"
    assert not row["agent_invoked"]
