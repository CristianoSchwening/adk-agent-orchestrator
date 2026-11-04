"""C03 — avalia PDFs locais em baseline E01, sem modificar os arquivos de origem."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from experiments.e01_prompt_injection.agent import create_agent
from experiments.e01_prompt_injection.run import APP_NAME, execute_case

DEFAULT_DIR = Path("data/experiments/e01/c03")
DEFAULT_OUTPUT = Path("data/executions/e01/c03/results.jsonl")


def load_pdf(path: Path) -> tuple[str, str, list[bytes]]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF ausente. Instale no ambiente virtual: "
            r".venv\Scripts\python.exe -m pip install PyMuPDF"
        ) from exc

    if not path.is_file():
        raise FileNotFoundError(f"PDF nao encontrado: {path}")
    with fitz.open(path) as pdf:
        if pdf.page_count == 0:
            raise ValueError(f"PDF sem paginas: {path}")
        text = "\n".join(page.get_text("text") for page in pdf)
        rendered = [
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).samples
            for page in pdf
        ]
    return text, hashlib.sha256(path.read_bytes()).hexdigest(), rendered


def prepare_cases(control_pdf: Path, attack_pdf: Path) -> tuple[list[dict], dict]:
    clean_text, clean_sha, clean_render = load_pdf(control_pdf)
    attack_text, attack_sha, attack_render = load_pdf(attack_pdf)
    if not clean_text.strip() or not attack_text.strip():
        raise ValueError("Extracao textual vazia: confira a estrutura dos PDFs")
    visible_equal = clean_render == attack_render
    report = {
        "control_pdf": str(control_pdf),
        "attack_pdf": str(attack_pdf),
        "control_pdf_sha256": clean_sha,
        "attack_pdf_sha256": attack_sha,
        "visible_render_identical": visible_equal,
        "extracted_text_identical": clean_text == attack_text,
        "control_text_sha256": hashlib.sha256(clean_text.encode()).hexdigest(),
        "attack_text_sha256": hashlib.sha256(attack_text.encode()).hexdigest(),
        "control_extracted_text": clean_text,
        "attack_extracted_text": attack_text,
    }
    cases = [
        {
            "id": "C03_CTRL" if index == 0 else "C03",
            "variant": "pdf_control" if index == 0 else "pdf_adversarial",
            "documents": [{
                "source_id": "P-003",
                "type": "pdf_extracted_text",
                "text": text,
            }],
        }
        for index, text in enumerate((clean_text, attack_text))
    ]
    return cases, report


async def main() -> int:
    from dotenv import load_dotenv
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    load_dotenv()
    parser = argparse.ArgumentParser(description="E01/C03: PDFs locais vs Gemini")
    parser.add_argument("--control-pdf", type=Path, default=DEFAULT_DIR / "controle.pdf")
    parser.add_argument("--attack-pdf", type=Path, default=DEFAULT_DIR / "adversarial.pdf")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=None)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 5:
        parser.error("--repetitions deve estar entre 1 e 5")
    model = args.model or os.getenv("E01_GEMINI_MODEL") or os.getenv("ADK_MODEL_WORKER")
    if not model:
        parser.error("Informe --model ou configure E01_GEMINI_MODEL/ADK_MODEL_WORKER")
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        parser.error("Configure GOOGLE_API_KEY ou GEMINI_API_KEY no .env")

    try:
        cases, report = prepare_cases(args.control_pdf, args.attack_pdf)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    diagnostic_path = args.output.with_name("pdf_extraction_diagnostic.json")
    diagnostic_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Renderizacao visual identica:", report["visible_render_identical"])
    print("Extracao textual identica:", report["extracted_text_identical"])
    print("Diagnostico:", diagnostic_path)
    if not report["visible_render_identical"]:
        print("ATENCAO: aparencia visual difere; avaliar antes de comparar respostas.")
    if report["extracted_text_identical"]:
        print("ATENCAO: extracao textual identica; nao ha diferenca textual testavel.")

    runner = Runner(
        app=App(name=APP_NAME, root_agent=create_agent(model)),
        session_service=InMemorySessionService(),
    )
    errors = 0
    for case in cases:
        for repetition in range(1, args.repetitions + 1):
            record = await execute_case(runner, case, model, repetition)
            record["ingestion_method"] = "PyMuPDF get_text(text)"
            record["source_pdf_sha256"] = (
                report["control_pdf_sha256"] if case["id"] == "C03_CTRL"
                else report["attack_pdf_sha256"]
            )
            record["visual_parity_with_control"] = report["visible_render_identical"]
            with args.output.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"{case['id']} #{repetition}: {record['status']} "
                f"({record['duration_seconds']:.1f}s) -> {args.output}"
            )
            errors += record["status"] != "ok"
    print("Avaliacao humana pendente; respostas nao pontuadas.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
