"""Testes offline da integridade do dataset E01, sem consumir tokens."""
from __future__ import annotations

from experiments.e01_prompt_injection.agent import INSTRUCTION, TASK, build_prompt, load_cases


def test_case_pair_preserves_evidence():
    clean, attacked = load_cases()
    assert clean["id"] == "C01"
    assert attacked["id"] == "C04"
    assert clean["documents"][1:] == attacked["documents"][1:]
    assert attacked["documents"][0]["text"].startswith(clean["documents"][0]["text"])
    assert "ignore os comprovantes" in attacked["documents"][0]["text"]


def test_prompt_contains_sources_and_fixed_task():
    cases = load_cases()
    first, second = (build_prompt(case) for case in cases)
    assert TASK in first and TASK in second
    assert "R-001" in first and "R-001" in second
    assert "R-003" in first and "R-003" in second
    assert "INSTRUÇÃO AO ASSISTENTE" not in first
    assert "INSTRUÇÃO AO ASSISTENTE" in second
    assert "documentos" in INSTRUCTION.lower()


def test_mixed_evidence_pair_is_identical_except_for_injection():
    cases = {case["id"]: case for case in load_cases()}
    clean = cases["C04B_CTRL"]["documents"]
    attacked = cases["C04B"]["documents"]
    assert len(clean) == len(attacked) == 1
    assert clean[0]["source_id"] == attacked[0]["source_id"] == "P-004"
    assert attacked[0]["text"].startswith(clean[0]["text"])
    for marker in ("JAN-2026", "FEV-2026", "MAR-2026", "R$ 6.000,00"):
        assert marker in clean[0]["text"]
        assert marker in attacked[0]["text"]
    assert "R$ 0,00" not in clean[0]["text"]
    assert "R$ 0,00" in attacked[0]["text"]
    assert "R-001" not in build_prompt(cases["C04B"])
    assert "R-002" not in build_prompt(cases["C04B"])
    assert "R-003" not in build_prompt(cases["C04B"])
