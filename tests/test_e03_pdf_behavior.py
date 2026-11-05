"""Testes E03: PDF, paridade visual, texto extraído e métricas offline."""
import json

import pytest

from experiments.e02_behavior import run as e02
from experiments.e03_pdf_behavior import generate, run


def test_pdf_triad_preserves_facts_and_invariants(tmp_path):
    cases, diag = generate.prepare(tmp_path)
    assert len(cases) == 3
    assert all(diag["invariants"].values())
    clean, hidden, quoted = cases
    assert clean["render_sha256"] == hidden["render_sha256"]
    assert clean["extracted_text_sha256"] != hidden["extracted_text_sha256"]
    assert clean["render_sha256"] != quoted["render_sha256"]
    assert "INSTRUCAO AO AGENTE" not in clean["documents"][0]["text"]
    assert "INSTRUCAO AO AGENTE" in hidden["documents"][0]["text"]
    assert "REGISTRO DE AUDITORIA" in quoted["documents"][0]["text"]
    assert len(list(tmp_path.glob("*.pdf"))) == 3


def test_pdf_generation_reproducible_for_resume(tmp_path):
    first, _ = generate.prepare(tmp_path)
    second, _ = generate.prepare(tmp_path)
    for a, b in zip(first, second):
        assert a["pdf_sha256"] == b["pdf_sha256"]
        assert a["render_sha256"] == b["render_sha256"]
        assert a["extracted_text_sha256"] == b["extracted_text_sha256"]


def test_same_task_agent_and_schema_as_e02(tmp_path):
    cases, _ = generate.prepare(tmp_path)
    assert run.TASK is e02.TASK
    assert run.INSTRUCTION is e02.INSTRUCTION
    assert run.build_prompt is e02.build_prompt
    record = {
        "valor_alegado_brl": 6000,
        "quantidade_lancamentos": 3,
        "fontes_lancamentos": ["P-004"],
        "comprovantes_separados_identificados": 0,
        "valor_confirmado_bancariamente_brl": None,
        "observacao_probatoria": "Somente extrato sintético, não confirmado.",
    }
    assert e02.validate_response(json.dumps(record))["contract_valid"]
    assert run.assess(cases[0], record)["fidelity_pass"]


def test_e03_history_rejects_changed_pdf_and_model(tmp_path):
    cases, _ = generate.prepare(tmp_path)
    row = {
        **run.e03_fingerprint(cases[0], "fake", 1),
        "status": "ok", "contract_valid": True,
    }
    assert run.select_e03_history([row], cases, "fake", 1)
    with pytest.raises(ValueError, match="incompatível"):
        run.select_e03_history([row], cases, "other", 1)
    with pytest.raises(ValueError, match="incompatível"):
        run.select_e03_history([dict(row, pdf_sha256="changed")], cases, "fake", 1)


def test_paired_comparison_cannot_assert_causal_attribution(tmp_path):
    cases, diag = generate.prepare(tmp_path)
    latest = {}
    rows = []
    for case in cases:
        parsed = {
            "valor_alegado_brl": 6000,
            "quantidade_lancamentos": 3,
            "fontes_lancamentos": ["P-004"],
            "comprovantes_separados_identificados": 0,
            "valor_confirmado_bancariamente_brl": None,
            "observacao_probatoria": "Dados sintéticos.",
        }
        row = {
            **run.e03_fingerprint(case, "fake", 1),
            "status": "ok", "contract_valid": True, "parsed": parsed,
        }
        rows.append(row)
        latest[(case["case_id"], 1)] = row
    result = run.summarize(latest, rows, cases, 1, "fake", diag)
    assert result["complete"] and len(result["paired_comparisons"]) == 1
    assert result["paired_comparisons"][0]["causal_attribution"] == "not_established"
