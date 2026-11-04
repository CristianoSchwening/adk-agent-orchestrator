"""A07: correspondência entre texto visual conhecido e camada OCR invisível.

Controle sintético: NÃO realiza OCR sobre os pixels nem classifica ataques.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from difflib import SequenceMatcher
from pathlib import Path

import fitz

from experiments.pdf_representation.a06_ocr import (
    FONT_SIZE, LINES, PAGE_HEIGHT, PAGE_WIDTH, STEP, X, Y0,
)

DEFAULT_DIR = Path("data/executions/pdf_representation/a07")
EXTRA_LINE = "MARCADOR EXTRA A07 SEM CORRESPONDENCIA VISUAL"
OCR_ALTERED = "FEV-2O26 | R$ 2.000,00"  # letra O substitui zero


def make_fixture(output_dir: Path) -> dict[str, Path]:
    """Renderiza uma imagem e a reutiliza com três camadas OCR invisíveis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with fitz.open() as source:
        page = source.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        for index, text in enumerate(LINES):
            page.insert_text((X, Y0 + index * STEP), text, fontsize=FONT_SIZE)
        image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")

    variants = {
        "A07_CTRL": tuple(LINES),
        "A07_DIFF": (*LINES, EXTRA_LINE),
        "A07_OCR": tuple(
            OCR_ALTERED if text.startswith("FEV-2026") else text for text in LINES
        ),
    }
    paths: dict[str, Path] = {}
    for case_id, texts in variants.items():
        path = output_dir / f"{case_id}.pdf"
        with fitz.open() as pdf:
            page = pdf.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_image(page.rect, stream=image)
            for index, text in enumerate(texts):
                page.insert_text(
                    (X, Y0 + index * STEP), text,
                    fontsize=FONT_SIZE, render_mode=3,
                )
            pdf.save(path)
        paths[case_id] = path
    return paths


def compare_lines(expected: list[str], actual: list[str]) -> dict:
    """Descreve diferenças, sem inferir malícia ou causa de erro OCR."""
    matcher = SequenceMatcher(a=expected, b=actual, autojunk=False)
    observations = []
    for op, i0, i1, j0, j1 in matcher.get_opcodes():
        if op == "equal":
            continue
        if op == "replace" and i1 - i0 == j1 - j0 == 1:
            kind = "line_substitution"
            similarity = round(
                SequenceMatcher(None, expected[i0], actual[j0]).ratio(), 4
            )
        else:
            kind = {
                "insert": "additional_extracted_text",
                "delete": "missing_extracted_text",
                "replace": "multi_line_replacement",
            }[op]
            similarity = None
        observations.append({
            "kind": kind,
            "visible_line_start": i0 + 1,
            "extracted_line_start": j0 + 1,
            "visible": expected[i0:i1],
            "extracted": actual[j0:j1],
            "similarity": similarity,
            "requires_review": True,
        })
    return {"exact_match": not observations, "observations": observations}


def run(output_dir: Path = DEFAULT_DIR) -> dict:
    paths = make_fixture(output_dir)
    rendered = []
    conditions = []
    ground_truth = {
        "A07_CTRL": "visible_text_corresponds_to_extracted_text",
        "A07_DIFF": "invisible_extra_text_not_in_image",
        "A07_OCR": "benign_simulated_ocr_character_error",
    }
    for case_id, path in paths.items():
        with fitz.open(path) as pdf:
            page = pdf[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            rendered.append(
                (pix.width, pix.height, hashlib.sha256(pix.samples).hexdigest())
            )
            extracted = [
                line for line in page.get_text("text").splitlines() if line.strip()
            ]
            invisible_count = sum(
                span.get("type") == 3 for span in page.get_texttrace()
            )
            conditions.append({
                "case_id": case_id,
                "fixture_ground_truth": ground_truth[case_id],
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "extracted_lines": extracted,
                "invisible_span_count": invisible_count,
                **compare_lines(list(LINES), extracted),
            })
    report = {
        "experiment": "A07",
        "visual_parity_all_three": len(set(rendered)) == 1,
        "visual_ground_truth_lines": list(LINES),
        "conditions": conditions,
        "interpretation_limits": [
            "Texto visual esperado é conhecido pela geração da fixture; não houve OCR dos pixels.",
            "Divergência textual não demonstra intenção adversarial nem prompt injection.",
            "OCR real pode introduzir diferenças de ordem, segmentação e omissões.",
        ],
    }
    (output_dir / "a07_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="A07: correspondência visual/textual controlada")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    report = run(args.output_dir)
    for condition in report["conditions"]:
        print(
            f"{condition['case_id']}: spans={condition['invisible_span_count']}, "
            f"exato={condition['exact_match']}, "
            f"divergências={len(condition['observations'])}"
        )
    print("Paridade visual:", report["visual_parity_all_three"])
    print("Relatório:", args.output_dir / "a07_report.json")
    if not report["visual_parity_all_three"]:
        raise SystemExit("Falha de paridade visual")


if __name__ == "__main__":
    main()
