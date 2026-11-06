"""Testes E14 sem chamadas externas; comparação e contratos."""
import json
from pathlib import Path

import pytest

from experiments.e14_native_pdf.run import (
    ARMS,
    CASES,
    fingerprint,
    existing_history,
    prepare,
    reference_text,
    report_for,
    validate,
)


def valid_response():
    return {
        "valores_alegados_brl": [1500, 200],
        "fontes_identificadas": ["P-013"],
        "instrucao_ia_detectada": False,
        "enquadramento_instrucao": "none",
        "evidencia_instrucao": None,
        "paginas_nao_verificadas": [],
        "observacao": "Informações alegadas sem confirmação externa.",
    }


def test_real_pdfs_and_reference_extraction(tmp_path):
    cases = prepare(tmp_path, allow_generate=True)
    assert len(cases) == len(CASES)
    assert len(ARMS) == 2
    assert "%PDF" in Path(cases["e13__mixed_page"]["path"]).read_bytes()[:10].decode()
    assert "R$ 1.500,00" in reference_text(Path(cases["e13__mixed_page"]["path"]))
    assert "R$ 200,00" not in reference_text(Path(cases["e13__mixed_page"]["path"]))


def test_validate_and_comparison_without_claiming_behavior(tmp_path):
    cases = prepare(tmp_path, allow_generate=True)
    parsed = validate(json.dumps(valid_response()))
    assert parsed["contract_valid"]
    assert not validate('{"foo":1}')["contract_valid"]
    cid = "e13__mixed_page"
    results = {
        (cid, arm): {"status": "ok", **parsed} for arm in ARMS
    }
    report = report_for(cases, results, "fake", [cid])
    assert report["complete"]
    assert report["valid_calls"] == 2
    assert all(r.get("behavioral_attack_followed") is None for r in report["rows"])


def test_history_rejects_changed_model_or_hash(tmp_path):
    cases = prepare(tmp_path / "pdfs", allow_generate=True)
    case = cases["e12__white_on_white"]
    ref = reference_text(Path(case["path"]))
    row = {**fingerprint(case, "native_pdf", "model-a", ref),
           "status": "ok", "contract_valid": True,
           "parsed": valid_response()}
    history = tmp_path / "history.jsonl"
    history.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert existing_history(history, cases, "model-a")
    with pytest.raises(ValueError, match="fingerprint"):
        existing_history(history, cases, "model-b")


def test_cannot_regenerate_missing_pdf_with_history(tmp_path):
    cases = prepare(tmp_path / "pdfs", allow_generate=True)
    Path(cases["e12__white_on_white"]["path"]).unlink()
    with pytest.raises(ValueError, match="ausentes"):
        prepare(tmp_path / "pdfs", allow_generate=False)
