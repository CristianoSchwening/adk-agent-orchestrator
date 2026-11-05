"""Testes offline E04 para PDFs e validação comportamental."""
import json

import pytest

from experiments.e02_behavior import run as e02
from experiments.e04_authority_pdf import generate, run


def test_six_pdf_conditions_and_invariants(tmp_path):
    cases, diagnostic = generate.prepare(tmp_path)
    assert len(cases) == 6
    assert {c["family"] for c in cases} == set(generate.MECHANISMS)
    assert all(all(flags.values()) for flags in diagnostic["invariants"].values())
    for mechanism in generate.MECHANISMS:
        by_variant = {
            c["variant"]: c for c in cases if c["family"] == mechanism
        }
        assert set(by_variant) == set(generate.VARIANTS)
        assert by_variant["control"]["render_sha256"] == by_variant["hidden_active"]["render_sha256"]
        assert by_variant["control"]["render_sha256"] != by_variant["visible_quoted"]["render_sha256"]


def test_attack_present_and_quote_framing(tmp_path):
    cases, _ = generate.prepare(tmp_path)
    for mechanism in generate.MECHANISMS:
        group = {c["variant"]: c for c in cases if c["family"] == mechanism}
        clean = group["control"]["documents"][0]["text"]
        attack = group["hidden_active"]["documents"][0]["text"]
        quote = group["visible_quoted"]["documents"][0]["text"]
        assert clean in attack and clean in quote
        for line in generate.MECHANISMS[mechanism]["attack_lines"]:
            assert line in attack and line in quote and line not in clean
        assert "CITACAO, NAO ORDEM" in quote


def test_generation_reproducible(tmp_path):
    first, _ = generate.prepare(tmp_path)
    second, _ = generate.prepare(tmp_path)
    assert [c["pdf_sha256"] for c in first] == [c["pdf_sha256"] for c in second]


def test_same_agent_task_and_rubric(tmp_path):
    cases, _ = generate.prepare(tmp_path)
    assert run.INSTRUCTION == e02.INSTRUCTION
    assert run.TASK == e02.TASK
    parsed = {
        "valor_alegado_brl": 6000, "quantidade_lancamentos": 3,
        "fontes_lancamentos": ["P-004"],
        "comprovantes_separados_identificados": 0,
        "valor_confirmado_bancariamente_brl": None,
        "observacao_probatoria": "Fatos fictícios sem comprovantes externos.",
    }
    assert e02.validate_response(json.dumps(parsed))["contract_valid"]
    assert all(run.assess(case, parsed)["fidelity_pass"] for case in cases)


def test_resume_and_comparison(tmp_path):
    cases, diagnostic = generate.prepare(tmp_path)
    parsed = {
        "valor_alegado_brl": 6000, "quantidade_lancamentos": 3,
        "fontes_lancamentos": ["P-004"],
        "comprovantes_separados_identificados": 0,
        "valor_confirmado_bancariamente_brl": None,
        "observacao_probatoria": "Sem validação independente.",
    }
    rows = [{
        **run.fingerprint(case, "fake-model", 1),
        "status": "ok", "contract_valid": True, "parsed": parsed,
    } for case in cases]
    latest = run.select_history(rows, cases, "fake-model", 1)
    assert len(latest) == 6
    report = run.summarize(latest, rows, cases, 1, "fake-model", diagnostic)
    assert report["complete"] and len(report["paired_comparisons"]) == 2
    assert all(not r["hidden_active_minus_control_deviation"]
               for r in report["paired_comparisons"])
    assert all(r["causal_attribution"] == "not_established"
               for r in report["paired_comparisons"])
    with pytest.raises(ValueError, match="incompatível"):
        run.select_history(rows, cases, "different-model", 1)
