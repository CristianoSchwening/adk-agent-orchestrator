"""E06: inferência Gemini com prompt B03 congelado e política E05."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.instructional_nature.b02 import is_retryable_503, read_history
from experiments.instructional_nature.b03 import (
    INSTRUCTION,
    build_prompt,
    validate_output,
)

from .cases import CASES
from .evaluate import fingerprint, report, select_history

DEFAULT_OUTPUT = Path("data/executions/e06/classifier_results.jsonl")
DEFAULT_REPORT = Path("data/executions/e06/triage_report.json")


async def execute(runner, model: str, case: tuple, repetition: int) -> dict:
    from google.genai import types

    cid, excerpt, _, _, _ = case
    row = {
        **fingerprint(case, model, repetition),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "error", "response": "", "error": None,
        "parsed": None, "contract_valid": False,
    }
    start = perf_counter()
    try:
        session = await runner.session_service.create_session(
            app_name="e06_triage_study", user_id="e06_research",
            session_id=f"e06-{uuid4().hex}",
        )
        parts = []
        async for event in runner.run_async(
            user_id="e06_research", session_id=session.id,
            new_message=types.Content(
                role="user", parts=[
                    types.Part.from_text(text=build_prompt(cid, excerpt))
                ],
            ),
        ):
            if event.is_final_response() and event.content:
                parts.extend(
                    part.text for part in (event.content.parts or []) if part.text
                )
        row["response"] = "\n".join(parts).strip()
        row["status"] = "ok" if row["response"] else "empty_response"
        if row["status"] == "ok":
            row.update(validate_output(row["response"], excerpt))
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["duration_seconds"] = round(perf_counter() - start, 3)
    return row


async def execute_with_retries(
    runner, model: str, case: tuple, repetition: int, max_attempts: int
) -> dict:
    attempts = []
    result = None
    for attempt in range(1, max_attempts + 1):
        result = await execute(runner, model, case, repetition)
        attempts.append({
            "attempt": attempt, "status": result["status"],
            "error": result.get("error"),
        })
        if result["status"] != "error" or not is_retryable_503(result.get("error")):
            break
        if attempt < max_attempts:
            await asyncio.sleep(min(60, 8 * 2 ** (attempt - 1)))
    result["attempts_made"] = len(attempts)
    result["retry_history"] = attempts
    return result


async def main() -> int:
    from dotenv import load_dotenv
    from google.adk.agents import LlmAgent
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    load_dotenv()
    parser = argparse.ArgumentParser(description="E06: classificador real e triagem E05")
    parser.add_argument("--model")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--pause-seconds", type=float, default=15)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 3:
        parser.error("--repetitions deve estar entre 1 e 3")
    if args.pause_seconds < 0 or not 1 <= args.max_attempts <= 6:
        parser.error("--pause-seconds ou --max-attempts inválidos")
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases deve ser positivo")
    if args.output.resolve() == args.report.resolve():
        parser.error("Saída JSONL e relatório não podem compartilhar o caminho")
    forbidden = {
        Path("data/executions/instructional_nature/b02_results.jsonl").resolve(),
        Path("data/executions/instructional_nature/b03_results.jsonl").resolve(),
        Path("data/executions/instructional_nature/b04_results.jsonl").resolve(),
    }
    if args.output.resolve() in forbidden:
        parser.error("Não sobrescreva históricos B02–B04")
    model = args.model or os.getenv("E01_GEMINI_MODEL") or os.getenv("ADK_MODEL_WORKER")
    if not model:
        parser.error("Informe --model ou variável E01_GEMINI_MODEL / ADK_MODEL_WORKER")
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        parser.error("Configure GOOGLE_API_KEY ou GEMINI_API_KEY")
    try:
        history = read_history(args.output)
        latest = select_history(history, model, args.repetitions)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    pending = [
        (case, rep) for rep in range(1, args.repetitions + 1)
        for case in CASES
        if (case[0], rep) not in latest or (
            latest[(case[0], rep)].get("status") != "ok"
            or latest[(case[0], rep)].get("contract_valid") is not True
        )
    ]
    if args.max_cases is not None:
        pending = pending[:args.max_cases]
    if pending:
        agent = LlmAgent(
            name="e06_document_classifier", model=model, tools=[],
            description="Classificação de trechos documentais usando B03 congelado",
            instruction=INSTRUCTION,
        )
        runner = Runner(
            app=App(name="e06_triage_study", root_agent=agent),
            session_service=InMemorySessionService(),
        )
        for index, (case, rep) in enumerate(pending):
            row = await execute_with_retries(
                runner, model, case, rep, args.max_attempts
            )
            history.append(row)
            latest[(case[0], rep)] = row
            with args.output.open("a", encoding="utf-8") as output:
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
            result = report(latest, history, model, args.repetitions)
            args.report.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"{case[0]} #{rep}: {row['status']} "
                f"JSON={row['contract_valid']}"
            )
            if index < len(pending) - 1 and args.pause_seconds:
                await asyncio.sleep(args.pause_seconds)
    result = report(latest, history, model, args.repetitions)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("E06 concluído:", result["complete"], "pendentes:", len(result["pending"]))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
