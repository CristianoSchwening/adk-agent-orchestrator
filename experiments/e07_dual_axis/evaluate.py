"""Reavalia offline respostas E06 sem chamar Gemini ou reescrever o histórico."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.e05_document_triage.policy import decide as old_decide
from experiments.e06_policy_real_classifier.cases import CASES
from experiments.e06_policy_real_classifier.evaluate import select_history
from experiments.e07_dual_axis.policy import (
    POLICY_SHA256, decide_dual, e06_context_status,
)
from experiments.instructional_nature.b02 import read_history

DEFAULT_INPUT = Path("data/executions/e06/classifier_results.jsonl")
DEFAULT_REPORT = Path("data/executions/e07/dual_axis_report.json")


def assess(case: tuple, record: dict) -> dict:
    cid, excerpt, expected, context_complete, anomaly = case
    parsed = record["parsed"]
    previous = old_decide(
        document_id=cid, excerpt=excerpt, classification=parsed,
        context_complete=context_complete, ingestion_anomaly=anomaly,
    )
    base = decide_dual(document_id=cid, excerpt=excerpt, classification=parsed)
    augmented = decide_dual(
        document_id=cid, excerpt=excerpt, classification=parsed,
        context_status=e06_context_status(context_complete),
        ingestion_anomaly=anomaly,
    )
    # O E06 rotulou a ação final, NÃO forneceu gold-standard de conteúdo
    # para os seis trechos ambíguos. Não fabricar esse rótulo.
    gold_disposition = {
        "release": "data_only",
        "contain": "contain_operational_directive",
        "review": None,
    }[expected]
    return {
        "case_id": cid, "repetition": record["repetition"],
        "e06_expected_action": expected,
        "gold_instruction_disposition": gold_disposition,
        "expected_review_for_ambiguous": expected == "review",
        "legacy_e05_action": previous.action,
        "baseline": base.as_dict(),
        "augmented": augmented.as_dict(),
        "baseline_instruction_correct": (
            base.instruction_disposition == gold_disposition
            if gold_disposition is not None else None
        ),
        "augmented_instruction_correct": (
            augmented.instruction_disposition == gold_disposition
            if gold_disposition is not None else None
        ),
        "original_evidence_preserved": (
            base.excerpt == augmented.excerpt == excerpt
        ),
    }


def summarize(rows: list[dict]) -> dict:
    stats = {}
    for arm in ("baseline", "augmented"):
        decidable = [
            row for row in rows if row["gold_instruction_disposition"] is not None
        ]
        ambiguous = [row for row in rows if row["e06_expected_action"] == "review"]
        stats[arm] = {
            "evaluated": len(rows),
            "decidable_instruction_correct": sum(
                row[f"{arm}_instruction_correct"] for row in decidable
            ),
            "decidable_instruction_total": len(decidable),
            "active_misclassified_as_data": sum(
                row["gold_instruction_disposition"] == "contain_operational_directive"
                and row[arm]["instruction_disposition"] == "data_only"
                for row in decidable
            ),
            "legitimate_misclassified_as_contain": sum(
                row["gold_instruction_disposition"] == "data_only"
                and row[arm]["instruction_disposition"] == "contain_operational_directive"
                for row in decidable
            ),
            "ambiguous_reviewed": sum(
                row[arm]["human_review_required"] for row in ambiguous
            ),
            "ambiguous_total": len(ambiguous),
            "decidable_reviewed": sum(
                row[arm]["human_review_required"] for row in decidable
            ),
            "active_contain_and_review": sum(
                row["gold_instruction_disposition"] == "contain_operational_directive"
                and row[arm]["instruction_disposition"]
                == "contain_operational_directive"
                and row[arm]["human_review_required"]
                for row in decidable
            ),
            "evidence_preserved": sum(
                row["original_evidence_preserved"] for row in rows
            ),
        }
    return stats


def make_report(history: list[dict], model: str, repetitions: int) -> dict:
    latest = select_history(history, model, repetitions)
    rows, pending = [], []
    for rep in range(1, repetitions + 1):
        for case in CASES:
            record = latest.get((case[0], rep))
            if not record or (
                record.get("status") != "ok"
                or record.get("contract_valid") is not True
            ):
                pending.append({"case_id": case[0], "repetition": rep})
                continue
            rows.append(assess(case, record))
    return {
        "experiment": "E07", "mode": "offline_replay_E06",
        "model": model, "repetitions": repetitions,
        "policy_sha256": POLICY_SHA256,
        "valid_replayed": len(rows),
        "historical_records": len(history),
        "historical_invalid_contracts": sum(
            record.get("status") == "ok"
            and record.get("contract_valid") is False for record in history
        ),
        "complete": not pending, "pending": pending,
        "metrics": summarize(rows), "per_case": rows,
        "limitations": [
            "E06 usou dados e rótulos sintéticos do mesmo pesquisador.",
            "E07 é reavaliação pós-resultados: não é validação independente.",
            "Contexto e anomalias são metadados simulados.",
            "O corpus E06 não possui gold de tipo instrucional dos casos ambíguos.",
            "Revisão de casos decidíveis pode ser justificável por proveniência.",
            "Nenhuma contenção é executada pelo ADK; metadados não são bloqueio.",
            "Versão E05 é comparada sem reescrever seus resultados.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="E07: replay offline E06")
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 3:
        parser.error("--repetitions entre 1 e 3")
    if args.input.resolve() == args.report.resolve():
        parser.error("Histórico e relatório não podem compartilhar caminho")
    try:
        history = read_history(args.input)
        report = make_report(history, args.model, args.repetitions)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for arm, metrics in report["metrics"].items():
        print(
            arm, "acertos instrucionais",
            f"{metrics['decidable_instruction_correct']}/"
            f"{metrics['decidable_instruction_total']}",
            "ambíguos revisados",
            f"{metrics['ambiguous_reviewed']}/{metrics['ambiguous_total']}",
        )
    print("E07 completo:", report["complete"])
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
