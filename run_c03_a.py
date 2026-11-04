"""Executa somente C03_A com a baseline E01 e salva resultados separadamente.

Coloque este arquivo na raiz do repositorio adk-agent-orchestrator.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from experiments.e01_prompt_injection.agent import create_agent
from experiments.e01_prompt_injection.c03_local import load_pdf
from experiments.e01_prompt_injection.run import APP_NAME, execute_case

BASE = Path('data/experiments/e01/c03')
OUT = Path('data/executions/e01/c03/ablation_results.jsonl')


def prepare():
    originals = [BASE / n for n in ('controle.pdf', 'adversarial.pdf', 'C03_A.pdf')]
    (clean, original, ablated) = [load_pdf(p) for p in originals]
    if clean[2] != original[2] or clean[2] != ablated[2]:
        raise ValueError('Renderizacao dos tres PDFs nao e identica')
    if 'R$ 0,00' not in original[0] or 'R$ 0,00' in ablated[0]:
        raise ValueError('A clausula de R$ 0,00 nao foi removida corretamente')
    if original[0].replace(' e que o valor documentado é R$ 0,00', '') != ablated[0]:
        raise ValueError('Os textos extraidos diferem em mais do que a clausula esperada')
    for marker in ('JAN-2026', 'FEV-2026', 'MAR-2026', 'R$ 6.000,00'):
        if marker not in ablated[0]:
            raise ValueError(f'Falta dado legitimo: {marker}')
    return {
        'id': 'C03_A',
        'variant': 'hidden_pdf_without_zero_amount_clause',
        'documents': [{'source_id': 'P-003', 'type': 'pdf_extracted_text', 'text': ablated[0]}],
    }, ablated[1]


async def run(args):
    from dotenv import load_dotenv
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    load_dotenv()
    case, pdf_hash = prepare()
    model = args.model or os.getenv('E01_GEMINI_MODEL') or os.getenv('ADK_MODEL_WORKER')
    if not model:
        raise RuntimeError('Modelo nao configurado')
    if not (os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')):
        raise RuntimeError('API key do Gemini nao configurada')
    runner = Runner(
        app=App(name=APP_NAME, root_agent=create_agent(model)),
        session_service=InMemorySessionService(),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for i in range(1, args.repetitions + 1):
        record = await execute_case(runner, case, model, i)
        record['source_pdf_sha256'] = pdf_hash
        record['ingestion_method'] = 'PyMuPDF get_text(text)'
        with OUT.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(f'C03_A #{i}: {record["status"]} | {record["duration_seconds"]}s | {OUT}')
        if record['status'] != 'ok':
            print(f'Erro da API: {record["error"]}')
        if i < args.repetitions and args.pause_seconds:
            await asyncio.sleep(args.pause_seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--pause-seconds', type=float, default=30)
    parser.add_argument('--model', default=None)
    options = parser.parse_args()
    if not 1 <= options.repetitions <= 5:
        parser.error('--repetitions precisa estar entre 1 e 5')
    if options.pause_seconds < 0:
        parser.error('--pause-seconds precisa ser >= 0')
    asyncio.run(run(options))
