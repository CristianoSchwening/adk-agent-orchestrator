"""Executor online do experimento E01.

Uso: python -m experiments.e01_prompt_injection.run --model gemini-2.5-flash
Não faz chamadas ao Gemini durante importação ou testes unitários.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.e01_prompt_injection.agent import (
    INSTRUCTION,
    build_prompt,
    create_agent,
    load_cases,
)

APP_NAME = "e01_prompt_injection"
USER_ID = "e01-local-evaluator"
DEFAULT_OUTPUT = Path("data/executions/e01/results.jsonl")


async def execute_case(runner, case: dict, model: str, repetition: int) -> dict:
    """Executa uma instância isolada com sessão nova e registra somente a resposta final."""
    from google.genai import types

    prompt = build_prompt(case)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=f"e01-{uuid4().hex}"
    )
    started = perf_counter()
    record = {
        "experiment": "E01",
        "case_id": case["id"],
        "variant": case["variant"],
        "repetition": repetition,
        "model": model,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "instruction_sha256": hashlib.sha256(INSTRUCTION.encode("utf-8")).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt": prompt,
        "status": "ok",
        "response": "",
        "error": None,
    }
    try:
        message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        responses = []
        async for event in runner.run_async(
            user_id=USER_ID, session_id=session.id, new_message=message
        ):
            if event.is_final_response() and event.content:
                responses.extend(
                    part.text for part in (event.content.parts or []) if part.text
                )
        record["response"] = "\n".join(responses)
        if not record["response"]:
            record["status"] = "empty_response"
    except Exception as exc:
        record["status"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["duration_seconds"] = round(perf_counter() - started, 3)
    return record


async def main() -> int:
    from dotenv import load_dotenv
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    load_dotenv()
    parser = argparse.ArgumentParser(description="E01: baseline documental com Gemini/ADK")
    parser.add_argument("--model", default=None, help="Modelo Gemini com acesso via API")
    parser.add_argument("--repetitions", type=int, default=1, help="Execuções por caso (1 a 5)")
    parser.add_argument("--cases", nargs="+", default=["C01", "C04"])
    parser.add_argument("--pause-seconds", type=float, default=2)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 5:
        parser.error("--repetitions deve estar entre 1 e 5")
    if args.pause_seconds < 0:
        parser.error("--pause-seconds não pode ser negativo")
    model = args.model or os.getenv("E01_GEMINI_MODEL") or os.getenv("ADK_MODEL_WORKER")
    if not model:
        parser.error("Informe --model ou E01_GEMINI_MODEL (escolha um modelo do tier gratuito)")
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        parser.error("Configure GOOGLE_API_KEY ou GEMINI_API_KEY no .env local")

    cases = load_cases()
    known = {case["id"]: case for case in cases}
    unknown = set(args.cases) - set(known)
    if unknown:
        parser.error(f"Casos desconhecidos: {', '.join(sorted(unknown))}")

    agent = create_agent(model)
    app = App(name=APP_NAME, root_agent=agent)
    runner = Runner(app=app, session_service=InMemorySessionService())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    failures = 0
    run_order = [known[case_id] for case_id in args.cases]
    for case in run_order:
        for repetition in range(1, args.repetitions + 1):
            record = await execute_case(runner, case, model, repetition)
            with args.output.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"{case['id']} #{repetition}: {record['status']} "
                f"({record['duration_seconds']:.1f}s) → {args.output}"
            )
            if record["status"] != "ok":
                failures += 1
            if args.pause_seconds and (case != run_order[-1] or repetition < args.repetitions):
                await asyncio.sleep(args.pause_seconds)
    print("Avaliação humana pendente; respostas foram registradas, não pontuadas.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
