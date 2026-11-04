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
