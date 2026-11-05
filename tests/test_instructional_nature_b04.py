"""B04: contrato congelado, corpus novo, abstensão e integridade."""
import json

import pytest

from experiments.instructional_nature import b03, b04


def parsed(**updates):
    obj = {
        "tipo_conteudo": "quoted_attack", "destinatario": "agent",
        "contem_instrucao_ia": True, "enquadramento": "quoted_or_reported",
        "tentativa_redirecionamento": False,
        "evidencia_textual": "texto", "requer_revisao": False,
    }
    obj.update(updates)
    return obj


def row(cid, obj):
    case = b04.CASE_INDEX[cid]
    return {
        **b04.fingerprint(case, "model-test", 1),
        "category": case[1],
        "ground_truth": (
            "agent_directive" if case[3] is True
            else "not_agent_directive" if case[3] is False else "indeterminate"
        ),
        "expected_review": case[4],
        "status": "ok", "contract_valid": True, "parsed": obj,
    }


def test_prompt_is_frozen_b03_unchanged():
    assert b04.INSTRUCTION is b03.INSTRUCTION
    assert b04.build_prompt is b03.build_prompt
    assert b04.validate_output is b03.validate_output


def test_corpus_has_new_cases_and_no_duplicates():
    assert len(b04.CASES) == 24
    assert len({case[0] for case in b04.CASES}) == 24
    assert len({case[2] for case in b04.CASES}) == 24
    assert all(case[0].startswith("B04_") for case in b04.CASES)
    assert sum(case[3] is True for case in b04.CASES) == 8
    assert sum(case[3] is False for case in b04.CASES) == 10
    assert sum(case[3] is None for case in b04.CASES) == 6


def test_binary_and_ambiguous_metrics_separated():
    rows = [
        row("B04_11", parsed(
            tipo_conteudo="agent_directive", enquadramento="active",
            tentativa_redirecionamento=True
        )),
        row("B04_08", parsed()),
        row("B04_19", parsed(
            tipo_conteudo="document_fact", enquadramento="ambiguous",
            contem_instrucao_ia=False, requer_revisao=True
        )),
    ]
    report = b04.aggregate(rows, requested=3)
    assert report["metrics_on_valid_decidable_only"] == {
        "true_positive": 1, "false_positive": 0, "true_negative": 1,
        "false_negative": 0, "category_matches": 2,
    }
    assert report["ambiguous_classifications"] == 1
    assert report["review_metrics"]["ambiguous_cases_flagged_for_review"] == 1
    assert report["per_case"][2]["binary_correct"] is None


def test_conflicted_context_suggests_review_without_relabel():
    item = parsed(tentativa_redirecionamento=True)
    report = b04.aggregate([row("B04_08", item)], requested=1)
    assert report["metrics_on_valid_decidable_only"]["false_positive"] == 1
    assert report["per_case"][0]["effective_review_suggested"]


def test_b03_historical_record_rejected():
    case = b04.CASE_INDEX["B04_01"]
    record = {**b04.fingerprint(case, "same", 1), "status": "ok"}
    assert b04.select_history([record], "same", 1)
    record["experiment"] = "B03"
    with pytest.raises(ValueError, match="incompatível"):
        b04.select_history([record], "same", 1)


def test_prompt_includes_only_excerpt_not_expected_label():
    case = b04.CASE_INDEX["B04_11"]
    prompt = b04.build_prompt(case[0], case[2])
    assert case[2] in prompt
    assert "expected_review" not in prompt
    assert "agent_directive" not in prompt


def test_contract_validation_still_strict():
    assert b04.validate_output(
        json.dumps(parsed()), "O laudo reproduz texto", )["contract_valid"]
    assert not b04.validate_output(
        json.dumps(parsed(evidencia_textual="não existe")), "texto"
    )["contract_valid"]
