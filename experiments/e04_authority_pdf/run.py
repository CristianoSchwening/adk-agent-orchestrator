"""E04: avaliação comportamental de autoridade fingida em PDFs.

Reusa agente E01, tarefa JSON E02 e avaliação E03; não inclui detector.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from experiments.e01_prompt_injection.agent import create_agent
from experiments.e02_behavior.run import (
    APP_NAME, INSTRUCTION, TASK, assess, build_prompt, read_history, sha,
)
from experiments.e03_pdf_behavior.run import (
    e03_fingerprint, run_case, select_e03_history,
)
from experiments.e04_authority_pdf.generate import OUTPUT_DIR, MECHANISMS, VARIANTS, prepare

DEFAULT_OUTPUT = Path("data/executions/e04/behavioral_results.jsonl")
DEFAULT_REPORT = Path("data/executions/e04/behavioral_report.json")


def fingerprint(case: dict, model: str, repetition: int) -> dict:
    value = e03_fingerprint(case, model, repetition)
    value["experiment"] = "E04"
    return value


def select_history(history: list[dict], cases: list[dict], model: str,
                   repetitions: int) -> dict:
    # E03 seleciona por hash, mas exige "E03"; substituímos apenas a
    # string na verificação, preservando os demais hashes e campos.
    converted = [{**row, "experiment": "E03"} for row in history]
    selected = select_e03_history(converted, cases, model, repetitions)
    return {key: {**row, "experiment": "E04"} for key, row in selected.items()}


def summarize(latest: dict, history: list[dict], cases: list[dict],
              repetitions: int, model: str, diagnostic: dict) -> dict:
    slots = [(case, rep) for rep in range(1, repetitions + 1) for case in cases]
    valid, pending = [], []
    for case, rep in slots:
        row = latest.get((case["case_id"], rep))
        if row is None or row.get("status") != "ok" or row.get("contract_valid") is not True:
            pending.append({"case_id": case["case_id"], "repetition": rep})
        else:
            valid.append({
                "case_id": case["case_id"], "mechanism": case["family"],
                "variant": case["variant"], "repetition": rep,
                **assess(case, row["parsed"]),
            })
    paired = []
    for mechanism in MECHANISMS:
        for rep in range(1, repetitions + 1):
            group = {
                record["variant"]: record
                for record in valid
                if record["mechanism"] == mechanism and record["repetition"] == rep
            }
            if set(group) != set(VARIANTS):
                continue
            control, active, quoted = (
                group["control"], group["hidden_active"], group["visible_quoted"]
            )
            paired.append({
                "mechanism": mechanism, "repetition": rep,
                "control_target_deviation": control["target_deviation_observed"],
                "hidden_active_target_deviation": active["target_deviation_observed"],
                "visible_quoted_target_deviation": quoted["target_deviation_observed"],
                "hidden_active_minus_control_deviation": (
                    active["target_deviation_observed"]
                    and not control["target_deviation_observed"]
                ),
                "visible_quoted_minus_control_deviation": (
                    quoted["target_deviation_observed"]
                    and not control["target_deviation_observed"]
                ),
                "causal_attribution": "not_established",
            })
    return {
        "experiment": "E04", "model": model, "repetitions": repetitions,
        "requested": len(slots), "valid_responses": len(valid),
        "historical_records": len(history),
        "historical_api_errors": sum(r.get("status") == "error" for r in history),
        "historical_invalid_contracts": sum(
            r.get("status") == "ok" and r.get("contract_valid") is False for r in history
        ),
        "diagnostic": diagnostic, "assessments": valid,
        "paired_comparisons": paired, "complete": not pending, "pending": pending,
        "instruction_sha256": sha(INSTRUCTION), "task_sha256": sha(TASK),
        "limitations": [
            "Ataques sintéticos com alegações fictícias de autoridade.",
            "O Gemini recebe texto extraído com PyMuPDF, não o PDF bruto.",
            "Paridade visual verificada exclusivamente pela renderização PyMuPDF.",
            "A proteção de fronteira de confiança já existe no agente E01.",
            "Rubrica estruturada reutilizada do E02 sem ajustes pós-resultados.",
            "Desvio observado não comprova seguimento de instrução nem causalidade.",
            "Amostra exploratória não estima resistência para produção.",
        ],
    }


async def main() -> int:
    from dotenv import load_dotenv
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    parser = argparse.ArgumentParser(description="E04: autoridade alegada em PDFs")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--pdf-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--model")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--pause-seconds", type=float, default=15)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 5 or args.pause_seconds < 0:
        parser.error("repetitions ou pause-seconds inválidos")
    if not 1 <= args.max_attempts <= 6 or (
        args.max_cases is not None and args.max_cases < 1
    ):
        parser.error("max-attempts ou max-cases inválidos")
    if args.output.resolve() == args.report.resolve():
        parser.error("output e report devem ser diferentes")
    try:
        cases, diagnostic = prepare(args.pdf_dir)
    except (ImportError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    (args.pdf_dir / "extraction_diagnostic.json").write_text(
        json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("E04: PDFs gerados; invariantes atendidas")
    if args.prepare_only:
        return 0
    load_dotenv()
    model = args.model or os.getenv("E01_GEMINI_MODEL") or os.getenv("ADK_MODEL_WORKER")
    if not model:
        parser.error("Informe --model ou E01_GEMINI_MODEL / ADK_MODEL_WORKER")
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        parser.error("Configure GOOGLE_API_KEY ou GEMINI_API_KEY")
    try:
        history = read_history(args.output)
        latest = select_history(history, cases, model, args.repetitions)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = [
        (case, rep) for rep in range(1, args.repetitions + 1)
        for case in cases if (
            (case["case_id"], rep) not in latest
            or latest[(case["case_id"], rep)].get("status") != "ok"
            or latest[(case["case_id"], rep)].get("contract_valid") is not True
        )
    ]
    if args.max_cases is not None:
        pending = pending[:args.max_cases]
    if pending:
        runner = Runner(
            app=App(name=APP_NAME, root_agent=create_agent(model)),
            session_service=InMemorySessionService(),
        )
        for index, (case, rep) in enumerate(pending):
            row = await run_case(runner, case, model, rep, args.max_attempts)
            row.update(fingerprint(case, model, rep))
            history.append(row)
            latest[(case["case_id"], rep)] = row
            with args.output.open("a", encoding="utf-8") as file:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
            report = summarize(latest, history, cases, args.repetitions, model, diagnostic)
            args.report.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"{case['case_id']} #{rep}: {row['status']}, "
                f"contrato={row['contract_valid']}"
            )
            if index < len(pending) - 1 and args.pause_seconds:
                await asyncio.sleep(args.pause_seconds)
    report = summarize(latest, history, cases, args.repetitions, model, diagnostic)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("E04 completo:", report["complete"], "pares:", len(report["paired_comparisons"]))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
