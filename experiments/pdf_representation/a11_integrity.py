"""A11: matriz determinística para revelar falsos negativos do pareamento A10.

As entradas simulam tokens OCR e tokens extraídos, com ground truth explícito.
Não executa OCR real; testes de integração em PDFs são trabalho posterior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.pdf_representation.a10_spatial import match_spatial

DEFAULT_OUTPUT = Path("data/executions/pdf_representation/a11/a11_report.json")


def token(text: str, x: float, y: float) -> dict:
    """Token com bbox compatível com o matcher A10 (coordenadas em pt)."""
    return {"text": text, "bbox": [x, y, x + 50, y + 10]}


def cases() -> list[dict]:
    """Ground truth é prescrito pelo experimento, não inferido pelo algoritmo."""
    return [
        {
            "case_id": "A11_AMOUNT_DIGIT",
            "category": "numeric_value_change",
            "visual": [token("2.000,00", 50, 100)],
            "embedded": [token("2.900,00", 50, 100)],
            "expected_discrepancy": True,
            "reason": "Dígito diferente altera valor financeiro",
        },
        {
            "case_id": "A11_DATE_DIGIT",
            "category": "date_change",
            "visual": [token("JAN-2026", 50, 100)],
            "embedded": [token("JAN-2028", 50, 100)],
            "expected_discrepancy": True,
            "reason": "Ano diferente altera referência temporal",
        },
        {
            "case_id": "A11_PUNCT_COLLISION",
            "category": "locale_sensitive_number",
            "visual": [token("1.234", 50, 100)],
            "embedded": [token("12,34", 50, 100)],
            "expected_discrepancy": True,
            "reason": "Normalização remove pontuação apesar de valores distintos",
        },
        {
            "case_id": "A11_CURRENCY_SYMBOL",
            "category": "punctuation_loss",
            "visual": [token("R$", 50, 100)],
            "embedded": [token("R", 50, 100)],
            "expected_discrepancy": True,
            "reason": "Símbolo monetário desaparece com a normalização",
        },
        {
            "case_id": "A11_NEAR_DISPLACEMENT",
            "category": "geometry_change",
            "visual": [token("R$ 6.000,00", 50, 100)],
            "embedded": [token("R$ 6.000,00", 61, 100)],
            "expected_discrepancy": True,
            "reason": "Deslocamento de 11pt ainda cabe no raio de correspondência",
        },
        {
            "case_id": "A11_REPEATED_VALUE",
            "category": "duplicate_token_perturbation",
            "visual": [
                token("2.000,00", 50, 100),
                token("2.000,00", 50, 140),
            ],
            "embedded": [
                token("2.000,00", 50, 100),
                token("2.900,00", 50, 140),
            ],
            "expected_discrepancy": True,
            "reason": "Token repetido não deve mascarar uma alteração localizada",
        },
        {
            "case_id": "A11_REPEATED_CONTROL",
            "category": "benign_duplicate_control",
            "visual": [
                token("2.000,00", 50, 100),
                token("2.000,00", 50, 140),
            ],
            "embedded": [
                token("2.000,00", 50, 140),
                token("2.000,00", 50, 100),
            ],
            "expected_discrepancy": False,
            "reason": "Mudança na ordem de extração sem alteração de conteúdo",
        },
    ]


def evaluate() -> dict:
    rows = []
    for case in cases():
        result = match_spatial(case["visual"], case["embedded"])
        signaled = result["review_items"] > 0
        expected = case["expected_discrepancy"]
        rows.append({
            "case_id": case["case_id"],
            "category": case["category"],
            "reason": case["reason"],
            "ground_truth_difference": expected,
            "visual_tokens": case["visual"],
            "embedded_tokens": case["embedded"],
            "a10_result": result,
            "signal_present": signaled,
            "false_negative": expected and not signaled,
            "false_positive": not expected and signaled,
        })
    positives = [r for r in rows if r["ground_truth_difference"]]
    negatives = [r for r in rows if not r["ground_truth_difference"]]
    false_negatives = sum(r["false_negative"] for r in rows)
    return {
        "experiment": "A11",
        "method": "deterministic token-level stress tests of A10 matcher",
        "cases": rows,
        "metrics": {
            "positive_cases": len(positives),
            "negative_controls": len(negatives),
            "detected_positive_cases": len(positives) - false_negatives,
            "false_negative_cases": false_negatives,
            "false_positive_cases": sum(r["false_positive"] for r in rows),
            "synthetic_detection_fraction": (
                round((len(positives) - false_negatives) / len(positives), 4)
                if positives else None
            ),
        },
        "limitations": [
            "Tokens e coordenadas são fabricados, não reconhecidos por OCR real.",
            "Ground truth descreve divergência de representações; não comprova ataque.",
            "Deslocamento espacial pode ser benigno em arquivos reais.",
            "A fração detectada é apenas desta matriz artificial, nunca taxa de produção.",
            "O código A10 permanece inalterado: objetivo é revelar falhas antes de corrigir.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A11: casos de falsos negativos espaciais")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for row in report["cases"]:
        label = (
            "FALSO NEGATIVO" if row["false_negative"]
            else "FALSO POSITIVO" if row["false_positive"]
            else "SINALIZADO" if row["signal_present"]
            else "SEM ALERTA"
        )
        print(f"{row['case_id']}: {label}")
    print("Falsos negativos:", report["metrics"]["false_negative_cases"])
    print("Relatório:", args.output)


if __name__ == "__main__":
    main()
