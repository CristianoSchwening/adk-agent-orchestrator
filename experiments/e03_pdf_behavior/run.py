"""E03: PDFs sintéticos -> extração PyMuPDF -> agente E01 -> auditoria E02."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from experiments.e01_prompt_injection.agent import create_agent
from experiments.e02_behavior.run import (
    APP_NAME as E02_APP,
    build_prompt,
    execute_with_retries,
    fingerprint,
    read_history,
    select_history,
    sha,
    TASK,
    INSTRUCTION,
    assess,
)
from experiments.e03_pdf_behavior.generate import OUTPUT_DIR, prepare

DEFAULT_OUTPUT = Path("data/executions/e03/behavioral_results.jsonl")
DEFAULT_REPORT = Path("data/executions/e03/behavioral_report.json")


def e03_fingerprint(case: dict, model: str, repetition: int) -> dict:
    original = fingerprint(case, model, repetition)
    return {
        **original,
        "experiment": "E03",
        "pdf_sha256": case["pdf_sha256"],
        "extracted_text_sha256": case["extracted_text_sha256"],
        "render_sha256": case["render_sha256"],
    }


def select_e03_history(history: list[dict], cases: list[dict],
                       model: str, repetitions: int) -> dict:
    by_id = {case["case_id"]: case for case in cases}
    latest = {}
    for lineno, row in enumerate(history, start=1):
        cid, rep = row.get("case_id"), row.get("repetition")
        if cid not in by_id or type(rep) is not int or rep < 1:
            raise ValueError(f"Histórico E03 inválido na linha {lineno}")
        expected = e03_fingerprint(by_id[cid], model, rep)
        diff = [key for key, value in expected.items() if row.get(key) != value]
        if diff:
            raise ValueError(f"Histórico E03 incompatível na linha {lineno}: {diff}")
        key = (cid, rep)
        current_ok = row.get("status") == "ok" and row.get("contract_valid") is True
        prev = latest.get(key)
        if current_ok or prev is None or not (
            prev.get("status") == "ok" and prev.get("contract_valid") is True
        ):
            latest[key] = row
    return {key: row for key, row in latest.items() if key[1] <= repetitions}


async def run_case(runner, case: dict, model: str, rep: int, attempts: int) -> dict:
    # Reutiliza o executor E02 (mesma tarefa JSON e agente E01).
    original = await execute_with_retries(runner, case, model, rep, attempts)
    original.update(e03_fingerprint(case, model, rep))
    original["ingestion_method"] = "PyMuPDF get_text(text)"
    return original


def summarize(latest: dict, history: list[dict], cases: list[dict],
              repetitions: int, model: str, diagnostic: dict) -> dict:
    slots = [(case, rep) for rep in range(1, repetitions + 1) for case in cases]
    valid = []
    pending = []
    for case, rep in slots:
        row = latest.get((case["case_id"], rep))
        if row is None or row.get("status") != "ok" or row.get("contract_valid") is not True:
            pending.append({"case_id": case["case_id"], "repetition": rep})
        else:
            valid.append({
                "case_id": case["case_id"], "variant": case["variant"],
                "repetition": rep,
                **assess(case, row["parsed"]),
            })
    comparison = []
    for rep in range(1, repetitions + 1):
        by_variant = {r["variant"]: r for r in valid if r["repetition"] == rep}
        if len(by_variant) != 3:
            continue
        base = by_variant["control"]
        active = by_variant["hidden_active"]
        quoted = by_variant["visible_quoted"]
        comparison.append({
            "repetition": rep,
            "control_target_deviation": base["target_deviation_observed"],
            "hidden_active_target_deviation": active["target_deviation_observed"],
            "visible_quoted_target_deviation": quoted["target_deviation_observed"],
            "hidden_active_minus_control_deviation": (
                active["target_deviation_observed"]
                and not base["target_deviation_observed"]
            ),
            "visible_quoted_minus_control_deviation": (
                quoted["target_deviation_observed"]
                and not base["target_deviation_observed"]
            ),
            "causal_attribution": "not_established",
        })
    return {
        "experiment": "E03",
        "model": model, "repetitions": repetitions,
        "requested": len(slots), "valid_responses": len(valid),
        "historical_records": len(history),
        "historical_api_errors": sum(r.get("status") == "error" for r in history),
        "historical_invalid_contracts": sum(
            r.get("status") == "ok" and r.get("contract_valid") is False
            for r in history
        ),
        "diagnostic": diagnostic,
        "assessments": valid, "paired_comparisons": comparison,
        "complete": not pending, "pending": pending,
        "instruction_sha256": sha(INSTRUCTION), "task_sha256": sha(TASK),
        "limitations": [
            "A aplicação extrai texto dos PDFs: NÃO envia o PDF binário ao Gemini.",
            "Paridade visual medida por renderização PyMuPDF, não por todo visualizador.",
            "O agente E01 já contém orientação para não seguir comandos documentais.",
            "Uma diferença entre respostas não demonstra por si só obediência ou causalidade.",
            "Dados e PDFs fictícios; nenhuma evidência de robustez em produção.",
            "Respostas JSON inválidas não são avaliadas semanticamente.",
        ],
    }


async def main() -> int:
    from dotenv import load_dotenv
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    parser = argparse.ArgumentParser(description="E03: PDF invisível e efeito comportamental")
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
        parser.error("repetitions (1–5) / pause-seconds (>=0) inválidos")
    if not 1 <= args.max_attempts <= 6:
        parser.error("max-attempts deve estar entre 1 e 6")
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("max-cases deve ser positivo")
    if args.output.resolve() == args.report.resolve():
        parser.error("output e report devem ser distintos")
    try:
        cases, diagnostic = prepare(args.pdf_dir)
    except (ImportError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    diagnostic_file = args.pdf_dir / "extraction_diagnostic.json"
    diagnostic_file.write_text(
        json.dumps(diagnostic, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("PDFs gerados e invariantes confirmadas:", diagnostic_file)
    if args.prepare_only:
        return 0
    load_dotenv()
    model = args.model or os.getenv("E01_GEMINI_MODEL") or os.getenv("ADK_MODEL_WORKER")
    if not model:
        parser.error("Informe --model ou configure E01_GEMINI_MODEL/ADK_MODEL_WORKER")
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        parser.error("Configure GOOGLE_API_KEY ou GEMINI_API_KEY no .env")
    try:
        history = read_history(args.output)
        latest = select_e03_history(history, cases, model, args.repetitions)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = [
        (case, rep) for rep in range(1, args.repetitions + 1)
        for case in cases
        if (case["case_id"], rep) not in latest
        or latest[(case["case_id"], rep)].get("status") != "ok"
        or latest[(case["case_id"], rep)].get("contract_valid") is not True
    ]
    if args.max_cases is not None:
        pending = pending[:args.max_cases]
    if pending:
        runner = Runner(
            app=App(name=E02_APP, root_agent=create_agent(model)),
            session_service=InMemorySessionService(),
        )
        for index, (case, rep) in enumerate(pending):
            row = await run_case(runner, case, model, rep, args.max_attempts)
            history.append(row)
            latest[(case["case_id"], rep)] = row
            with args.output.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            args.report.write_text(json.dumps(
                summarize(latest, history, cases, args.repetitions, model, diagnostic),
                indent=2, ensure_ascii=False,
            ), encoding="utf-8")
            print(f"{case['case_id']} #{rep}: {row['status']}, contrato={row['contract_valid']}")
            if index < len(pending) - 1 and args.pause_seconds:
                await asyncio.sleep(args.pause_seconds)
    report = summarize(latest, history, cases, args.repetitions, model, diagnostic)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Concluído:", report["complete"], "Pendentes:", len(report["pending"]))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
