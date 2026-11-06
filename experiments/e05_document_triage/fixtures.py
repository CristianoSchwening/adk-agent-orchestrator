"""Fixtures ilustrativas de E05, NÃO previsões reais do B03/B04."""
from __future__ import annotations

from experiments.instructional_nature.b04_cases import CASES


def sample_classification(excerpt: str, label: str) -> dict:
    """Dados simulados para testes de contrato, sem inferência do Gemini."""
    if label == "active":
        category = "agent_directive"
        framing = "active"
        redirect = present = True
        review = False
    elif label == "quoted":
        category = "quoted_attack"
        framing = "quoted_or_reported"
        redirect = False
        present = True
        review = False
    elif label == "ambiguous":
        category = "workflow_data"
        framing = "ambiguous"
        redirect = False
        present = False
        review = True
    elif label == "legal":
        category = "legal_request"
        framing = "none"
        redirect = present = review = False
    else:
        raise ValueError("Fixture desconhecida")
    return {
        "tipo_conteudo": category,
        "destinatario": (
            "agent" if label in {"active", "quoted"} else
            "court" if label == "legal" else "unclear"
        ),
        "contem_instrucao_ia": present,
        "enquadramento": framing,
        "tentativa_redirecionamento": redirect,
        "evidencia_textual": excerpt[: min(60, len(excerpt))],
        "requer_revisao": review,
    }


def examples() -> list[dict]:
    indices = (4, 8, 14, 19)
    labels = ("legal", "quoted", "active", "ambiguous")
    return [
        {
            "document_id": CASES[i][0],
            "excerpt": CASES[i][2],
            "classification": sample_classification(CASES[i][2], label),
            "context_complete": False if label == "ambiguous" else True,
        }
        for i, label in zip(indices, labels)
    ]
