"""A06: fixture reprodutível de OCR legítimo, sem dados reais ou serviços externos."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

PAGE_WIDTH, PAGE_HEIGHT = 595, 842
LINES = (
    "EXTRATO SINTETICO - DOCUMENTO FICTICIO",
    "JAN-2026 | R$ 2.000,00",
    "FEV-2026 | R$ 2.000,00",
    "MAR-2026 | R$ 2.000,00",
    "TOTAL INFORMADO: R$ 6.000,00",
    "SEM COMPROVANTES BANCARIOS INDEPENDENTES",
)
X, Y0, STEP, FONT_SIZE = 50, 95, 35, 11


def create_pair(folder: Path) -> tuple[Path, Path]:
    """PDFs visualmente iguais: página rasterizada pura e página com OCR invisível."""
    folder.mkdir(parents=True, exist_ok=True)
    with fitz.open() as original:
        page = original.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        for i, line in enumerate(LINES):
            page.insert_text((X, Y0 + i * STEP), line, fontsize=FONT_SIZE)
        image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")
    paths = folder / "A06_scan_only.pdf", folder / "A06_scan_with_ocr.pdf"
    for with_ocr, destination in enumerate(paths):
        with fitz.open() as pdf:
            page = pdf.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_image(page.rect, stream=image)
            if with_ocr:
                for i, line in enumerate(LINES):
                    page.insert_text(
                        (X, Y0 + i * STEP), line, fontsize=FONT_SIZE, render_mode=3
                    )
            pdf.save(destination)
    return paths


def report_pair(folder: Path) -> dict:
    """Compara o sinal estrutural do A01 com uma camada OCR benigna conhecida."""
    from experiments.pdf_representation.analyze import build_report

    clean, ocr = create_pair(folder)
    report = build_report(clean, ocr)
    comparison = report["comparison"]
    source = report["control"]["pages"][0]["extracted_text"]
    actual = report["candidate"]["pages"][0]["extracted_text"]
    summary = {
        "experiment": "A06",
        "classification_ground_truth": "benign_searchable_ocr",
        "paths": [str(clean), str(ocr)],
        "pdf_sha256": [
            hashlib.sha256(path.read_bytes()).hexdigest() for path in (clean, ocr)
        ],
        "visual_parity": comparison["visual_parity"],
        "extraction_difference": comparison["extraction_difference"],
        "hidden_spans_flagged_by_a01": comparison["candidate_flagged_spans"],
        "scan_without_ocr_extracts_empty_text": not source.strip(),
        "ocr_recovers_all_lines": all(line in actual for line in LINES),
        "interpretation": (
            "Texto invisível é sinal técnico; OCR alinhado à imagem pode ser legítimo."
        ),
    }
    (folder / "a06_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="A06: OCR benigno e falso positivo estrutural")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/executions/pdf_representation/a06"),
    )
    args = parser.parse_args()
    summary = report_pair(args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not (
        summary["visual_parity"]
        and summary["extraction_difference"]
        and summary["hidden_spans_flagged_by_a01"] > 0
        and summary["scan_without_ocr_extracts_empty_text"]
        and summary["ocr_recovers_all_lines"]
    ):
        raise SystemExit("Fixture A06 não passou nos critérios técnicos")


if __name__ == "__main__":
    main()
