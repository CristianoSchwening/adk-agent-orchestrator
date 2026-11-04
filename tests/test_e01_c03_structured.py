"""Testes do experimento C03 com resposta estruturada, sem chamada ao Gemini."""
import json
from pathlib import Path

from experiments.e01_prompt_injection import c03_structured


def test_prompt_contains_same_task_and_source():
    prompt = c03_structured.build_structured_prompt("JAN-2026 R$ 2.000,00")
    assert "valor_comprovado_independentemente_brl" in prompt
    assert "P-003" in prompt
    assert "JAN-2026" in prompt


def test_valid_json_with_unknown_independent_amount():
    response = json.dumps({
        "valor_alegado_brl": 6000,
        "valor_comprovado_independentemente_brl": None,
        "situacao_probatoria": "Sem comprovantes independentes",
        "fontes": ["P-003"],
    })
    assert c03_structured.inspect_response(response)["contract_valid"]


def test_zero_is_syntactically_valid_but_requires_human_review():
    response = json.dumps({
        "valor_alegado_brl": 6000,
        "valor_comprovado_independentemente_brl": 0,
        "situacao_probatoria": "Sem comprovantes independentes",
        "fontes": ["P-003"],
    })
    result = c03_structured.inspect_response(response)
    assert result["contract_valid"]
    assert result["parsed"]["valor_comprovado_independentemente_brl"] == 0


def test_prepare_sources(monkeypatch):
    def stub(path: Path):
        return "JAN-2026", "hash", [b"pixels"]

    monkeypatch.setattr(c03_structured, "load_pdf", stub)
    cases, report = c03_structured.prepare_sources([
        Path("controle.pdf"), Path("adversarial.pdf"), Path("C03_A.pdf")
    ])
    assert [case["id"] for case in cases] == ["C03_CTRL_S", "C03_S", "C03_A_S"]
    assert report["render_identical"]
