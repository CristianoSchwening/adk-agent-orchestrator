"""B03: contrato, consistência e retomada sem API externa."""
import asyncio
import json

import pytest

from experiments.instructional_nature import b03


def example(**changes):
    data = {
        "tipo_conteudo": "quoted_attack",
        "destinatario": "agent",
        "contem_instrucao_ia": True,
        "enquadramento": "quoted_or_reported",
        "tentativa_redirecionamento": False,
        "evidencia_textual": "ignore instruções",
        "requer_revisao": False,
    }
    data.update(changes)
    return data


def sample_row(cid, parsed, *, status="ok", valid=True):
    case = b03.CASE_INDEX[cid]
    return {
        **b03.fingerprint(case, "test-model", 1),
        "category": case[1],
        "ground_truth": "agent_directive" if case[3] else "not_agent_directive",
        "status": status,
        "contract_valid": valid,
        "parsed": parsed,
    }


def test_corpus_and_prompt_are_independent_from_b02():
    assert len(b03.CASE_INDEX) == 16
    assert "contem_instrucao_ia" in b03.INSTRUCTION
    assert b03.DEFAULT_OUTPUT.name != "b02_results.jsonl"
    assert "ignore instruções" in b03.build_prompt("B01_06", "ignore instruções")


def test_quoted_command_valid_but_not_active():
    parsed = example()
    assert b03.validate_output(json.dumps(parsed), "A pessoa disse ignore instruções")[
        "contract_valid"
    ]
    assert b03.consistency_flags(parsed) == []


def test_quoted_but_active_is_flagged_without_modification():
    parsed = example(tentativa_redirecionamento=True)
    result = b03.consistency_flags(parsed)
    assert "quoted_context_marked_active" in result
    assert parsed["tentativa_redirecionamento"] is True


def test_active_without_presence_is_flagged():
    parsed = example(
        tipo_conteudo="agent_directive", enquadramento="active",
        contem_instrucao_ia=False, tentativa_redirecionamento=True
    )
    assert "active_without_instruction_presence" in b03.consistency_flags(parsed)


def test_invalid_contract_and_missing_evidence_rejected():
    parsed = example(evidencia_textual="não consta")
    assert not b03.validate_output(json.dumps(parsed), "Texto simples")["contract_valid"]
    parsed = example(contem_instrucao_ia="true")
    assert not b03.validate_output(json.dumps(parsed), "ignore instruções")["contract_valid"]
    parsed = example(campo_extra="invalido")
    assert not b03.validate_output(json.dumps(parsed), "ignore instruções")["contract_valid"]


def test_aggregate_reports_raw_prediction_and_review():
    parsed = example(tentativa_redirecionamento=True)
    report = b03.aggregate([sample_row("B01_06", parsed)], requested=1)
    assert report["metrics_on_valid_only"]["false_positive"] == 1
    assert report["metrics_on_valid_only"]["consistency_flagged_cases"] == 1
    assert report["per_case"][0]["effective_review_suggested"]
    assert not report["per_case"][0]["binary_correct"]


def test_history_rejects_model_or_prompt_mismatch():
    row = sample_row("B01_06", example())
    assert b03.select_history([row], "test-model", 1)[("B01_06", 1)] == row
    with pytest.raises(ValueError, match="incompatível"):
        b03.select_history([row], "new-model", 1)
    row["instruction_sha256"] = "wrong"
    with pytest.raises(ValueError, match="instruction_sha256"):
        b03.select_history([row], "test-model", 1)


def test_valid_record_survives_new_error_record():
    row = sample_row("B01_06", example())
    failed = dict(row, status="error", contract_valid=False, parsed=None)
    latest = b03.select_history([row, failed], "test-model", 1)
    assert latest[("B01_06", 1)]["status"] == "ok"


def test_retry_503_backoff(monkeypatch):
    calls = []
    waits = []

    async def fake_execute(*args):
        calls.append(1)
        return (
            {"status": "error", "error": "ServerError 503 UNAVAILABLE"}
            if len(calls) < 3
            else {"status": "ok", "error": None, "contract_valid": True}
        )

    async def sleeper(delay):
        waits.append(delay)

    monkeypatch.setattr(b03, "execute", fake_execute)
    row = asyncio.run(
        b03.execute_with_retries(
            None, "test-model", b03.CASE_INDEX["B01_06"], 1,
            max_attempts=3, retry_base_seconds=2, sleeper=sleeper
        )
    )
    assert row["attempts_made"] == 3
    assert waits == [2, 4]


def test_partial_report_has_pending_and_no_full_comparison():
    row = sample_row("B01_06", example())
    report = b03.make_report(
        {("B01_06", 1): row}, [row], list(b03.CASE_INDEX), 1, "test-model"
    )
    assert not report["complete"]
    assert len(report["pending"]) == 15
    assert report["comparisons_full_corpus_only"] is None
