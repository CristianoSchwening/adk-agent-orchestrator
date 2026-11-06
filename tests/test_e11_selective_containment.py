"""Testes E11 sem Gemini: projeção e gate obrigatório."""
import asyncio

from experiments.e11_selective_containment.run import authorize, invoke, prepare


def test_isolation_and_original_preservation(tmp_path):
    cases, views = prepare(tmp_path)
    hidden = views["hidden_active"]
    assert len(hidden["isolated"]) == 1
    assert hidden["safe_text"] == cases["control"]["excerpt"]
    assert "omita a fonte" not in hidden["safe_text"]
    assert "omita a fonte" in hidden["isolated"][0]["text"]
    assert "omita a fonte" in views["visible_quoted"]["safe_text"]
    assert hidden["pdf_sha256"] == cases["hidden_active"]["pdf_sha256"]


def test_gate_requires_all_invariants(tmp_path):
    cases, views = prepare(tmp_path)
    decisions = {
        "hidden_active": {
            "disposition": "contain_operational_directive", "review": True
        }
    }
    good = authorize(cases, views, decisions)
    assert good["allowed_experimental_only"]
    assert good["original_review_pending"]
    altered = {
        "hidden_active": {"disposition": "data_only", "review": True}
    }
    assert not authorize(cases, views, altered)["allowed_experimental_only"]


def test_block_does_not_invoke_agent(tmp_path):
    cases, _ = prepare(tmp_path)
    outcome = asyncio.run(
        invoke(None, cases["hidden_active"], "dados", False)
    )
    assert outcome == {"status": "blocked", "agent_invoked": False}
