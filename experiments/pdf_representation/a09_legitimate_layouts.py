"""A09 — Robustez do comparador em documentos sintéticos legítimos.

Mede alertas em quatro layouts sem conteúdo adversarial.
O Tesseract lê pixels; PyMuPDF lê a camada de texto invisível.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

from experiments.pdf_representation.a08_independent_ocr import (
    compare_ocr_to_extracted,
    run_ocr,
)

DEFAULT_DIR = Path("data/executions/pdf_representation/a09")
PAGE = (595, 842)
CONTENT = (
    ("JAN-2026 | R$ 2.000,00", 52, 110),
    ("FEV-2026 | R$ 2.000,00", 52, 145),
    ("MAR-2026 | R$ 2.000,00", 52, 180),
    ("TOTAL: R$ 6.000,00", 52, 215),
)


def _make_page(case_id: str) -> list[tuple[str, float, float]]:
    if case_id == "A09_SINGLE":
        return list(CONTENT)
    if case_id == "A09_COLUMNS":
        return [
            ("DOCUMENTOS", 52, 95),
            ("JAN-2026 | R$ 2.000,00", 52, 135),
            ("FEV-2026 | R$ 2.000,00", 52, 170),
            ("COMPROVACAO", 325, 95),
            ("MAR-2026 | R$ 2.000,00", 325, 135),
            ("TOTAL: R$ 6.000,00", 325, 170),
        ]
    if case_id == "A09_TABLE":
        return [
            ("MES", 52, 98), ("VALOR", 320, 98),
            ("JAN-2026", 52, 137), ("R$ 2.000,00", 320, 137),
            ("FEV-2026", 52, 175), ("R$ 2.000,00", 320, 175),
            ("MAR-2026", 52, 213), ("R$ 2.000,00", 320, 213),
            ("TOTAL", 52, 251), ("R$ 6.000,00", 320, 251),
        ]
    if case_id == "A09_LOWRES":
        return list(CONTENT)
    raise ValueError(case_id)


def create_fixture(case_id: str, folder: Path) -> Path:
    """Mesmos dados visíveis e OCR legítimo; imagem em diferentes layouts/qualidades."""
    folder.mkdir(parents=True, exist_ok=True)
    entries = _make_page(case_id)
    with fitz.open() as src:
        page = src.new_page(width=PAGE[0], height=PAGE[1])
        if case_id == "A09_TABLE":
            for y in (108, 146, 184, 222, 260):
                page.draw_line((45, y), (475, y), color=(0, 0, 0), width=0.6)
        for content, x, y in entries:
            page.insert_text((x, y), content, fontsize=11)
        raster_scale = 0.85 if case_id == "A09_LOWRES" else 2.0
        pix = page.get_pixmap(matrix=fitz.Matrix(raster_scale, raster_scale), alpha=False)
        png = pix.tobytes("png")
    path = folder / f"{case_id}.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page(width=PAGE[0], height=PAGE[1])
        page.insert_image(page.rect, stream=png)
        for content, x, y in entries:
            page.insert_text((x, y), content, fontsize=11, render_mode=3)
        pdf.save(path)
    return path


def evaluate(
    folder: Path = DEFAULT_DIR, *,
    language: str = "eng",
    tesseract: str = "tesseract",
    threshold: float = 0.86,
) -> dict:
    conditions = []
    for case_id in ("A09_SINGLE", "A09_COLUMNS", "A09_TABLE", "A09_LOWRES"):
        path = create_fixture(case_id, folder)
        with fitz.open(path) as pdf:
            page = pdf[0]
            ocr = run_ocr(page, language=language, executable=tesseract)
            extracted = [s.strip() for s in page.get_text("text").splitlines() if s.strip()]
            comparison = compare_ocr_to_extracted(ocr["lines"], extracted, threshold)
            alert_count = (
                len(comparison["approximate_matches"])
                + len(comparison["unmatched_extracted"])
                + len(comparison["unmatched_ocr"])
            )
            conditions.append({
                "case_id": case_id,
                "ground_truth": "benign_no_adversarial_content",
                "pdf_path": str(path),
                "pdf_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "ocr_lines": ocr["lines"],
                "extracted_lines": extracted,
                "comparison": comparison,
                "alert_count": alert_count,
                "document_with_alert": alert_count > 0,
            })
    return {
        "experiment": "A09",
        "method": "Tesseract visual OCR versus PyMuPDF structural extraction",
        "conditions": conditions,
        "total_documents": len(conditions),
        "documents_with_alert": sum(int(c["document_with_alert"]) for c in conditions),
        "total_review_items": sum(c["alert_count"] for c in conditions),
        "config": {"language": language, "threshold": threshold},
        "limitations": [
            "Amostra pequena e sintética: não estimar taxa de falso positivo em produção.",
            "A ordem da camada OCR foi construída pelo gerador e pode afetar alinhamento.",
            "Alertas podem refletir OCR, layout, segmentação, qualidade ou comparador.",
            "Nenhum alerta significa ataque; todos os quatro documentos são benignos.",
            "Textos OCR e extraídos ficam no JSON local; não versionar PDFs ou relatórios.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A09: medir alertas em documentos legítimos")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--threshold", type=float, default=0.86)
    args = parser.parse_args()
    if not 0 < args.threshold <= 1:
        parser.error("--threshold deve estar entre 0 (exclusivo) e 1")
    report = evaluate(
        args.output_dir, language=args.language,
        tesseract=args.tesseract, threshold=args.threshold
    )
    destination = args.output_dir / "a09_report.json"
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for condition in report["conditions"]:
        print(f"{condition['case_id']}: {condition['alert_count']} alertas")
    print("Documentos com alerta:", report["documents_with_alert"])
    print("Itens para revisão:", report["total_review_items"])
    print("Relatório:", destination)


if __name__ == "__main__":
    main()
