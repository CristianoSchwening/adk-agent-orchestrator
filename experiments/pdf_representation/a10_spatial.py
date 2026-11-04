"""A10: correspondência espacial entre OCR e texto embutido em PDFs sintéticos."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
from difflib import SequenceMatcher
from pathlib import Path

import fitz

from experiments.pdf_representation.a07_correspondence import make_fixture
from experiments.pdf_representation.a08_independent_ocr import compare_ocr_to_extracted, run_ocr
from experiments.pdf_representation.a09_legitimate_layouts import create_fixture

DEFAULT_DIR = Path("data/executions/pdf_representation/a10")
CASES = ("A09_SINGLE", "A09_COLUMNS", "A09_TABLE", "A09_LOWRES", "A07_DIFF")


def norm(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def ocr_words(page, *, executable="tesseract", language="eng", scale=2.0):
    if shutil.which(executable) is None and not Path(executable).is_file():
        raise RuntimeError(f"Tesseract não encontrado: {executable}")
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    command = [executable, "stdin", "stdout", "--psm", "6", "-l", language, "tsv"]
    try:
        process = subprocess.run(
            command, input=pix.tobytes("png"), capture_output=True,
            timeout=60, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Tesseract excedeu 60 segundos") from exc
    if process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace")[:600])
    words = []
    reader = csv.DictReader(
        io.StringIO(process.stdout.decode("utf-8", errors="replace")), delimiter="\t"
    )
    for item in reader:
        if item.get("level") != "5" or not item.get("text", "").strip():
            continue
        x, y = float(item["left"]) / scale, float(item["top"]) / scale
        w, h = float(item["width"]) / scale, float(item["height"]) / scale
        words.append({
            "text": item["text"].strip(), "bbox": [x, y, x+w, y+h],
            "confidence": item.get("conf"),
        })
    return words


def extracted_words(page):
    return [
        {"text": item[4], "bbox": list(item[:4])}
        for item in page.get_text("words") if str(item[4]).strip()
    ]


def match_spatial(visual, extracted, *, similarity=0.76, max_distance=19.0):
    """Pareamento um-para-um; proximidade espacial é condição obrigatória."""
    candidates = []
    for vi, v in enumerate(visual):
        vx, vy = center(v["bbox"])
        for ei, e in enumerate(extracted):
            ex, ey = center(e["bbox"])
            distance = ((vx-ex)**2 + (vy-ey)**2)**0.5
            if distance > max_distance:
                continue
            a, b = norm(v["text"]), norm(e["text"])
            if not a or not b:
                if v["text"].strip() != e["text"].strip():
                    continue
                ratio = 1.0
            else:
                ratio = SequenceMatcher(None, a, b, autojunk=False).ratio()
            if ratio >= similarity:
                candidates.append((
                    ratio - 0.15*distance/max_distance, vi, ei,
                    ratio, round(distance, 2),
                ))
    candidates.sort(reverse=True)
    taken_v, taken_e, matched = set(), set(), []
    for _, vi, ei, ratio, distance in candidates:
        if vi in taken_v or ei in taken_e:
            continue
        taken_v.add(vi)
        taken_e.add(ei)
        matched.append((vi, ei, round(ratio, 4), distance))
    approximate = [
        {
            "ocr": visual[i], "embedded": extracted[j], "similarity": ratio,
            "distance_pt": distance, "requires_review": True,
        }
        for i, j, ratio, distance in matched
        if norm(visual[i]["text"]) != norm(extracted[j]["text"])
    ]
    unmatched_extracted = [
        dict(extracted[i], requires_review=True)
        for i in range(len(extracted)) if i not in taken_e
    ]
    unmatched_visual = [
        dict(visual[i], requires_review=True)
        for i in range(len(visual)) if i not in taken_v
    ]
    return {
        "matched_count": len(matched),
        "approximate_matches": approximate,
        "unmatched_extracted": unmatched_extracted,
        "unmatched_visual": unmatched_visual,
        "review_items": len(approximate)+len(unmatched_extracted)+len(unmatched_visual),
        "coverage": round(len(matched)/len(extracted), 4) if extracted else None,
        "parameters": {"min_similarity": similarity, "max_distance_pt": max_distance},
    }


def evaluate(folder=DEFAULT_DIR, *, language="eng", executable="tesseract",
             similarity=0.76, max_distance=19.0):
    folder.mkdir(parents=True, exist_ok=True)
    fixtures = {
        name: create_fixture(name, folder)
        for name in CASES if name.startswith("A09")
    }
    fixtures["A07_DIFF"] = make_fixture(folder)["A07_DIFF"]
    rows = []
    for case_id in CASES:
        path = fixtures[case_id]
        with fitz.open(path) as pdf:
            page = pdf[0]
            visual = ocr_words(page, executable=executable, language=language)
            embedded = extracted_words(page)
            spatial = match_spatial(
                visual, embedded, similarity=similarity, max_distance=max_distance
            )
            older = run_ocr(page, executable=executable, language=language)
            old_text = [
                line.strip() for line in page.get_text("text").splitlines()
                if line.strip()
            ]
            baseline = compare_ocr_to_extracted(older["lines"], old_text)
            baseline_count = sum(len(baseline[key]) for key in (
                "approximate_matches", "unmatched_extracted", "unmatched_ocr"
            ))
            rows.append({
                "case_id": case_id,
                "ground_truth": (
                    "invisible_additional_content" if case_id == "A07_DIFF"
                    else "benign"
                ),
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "ocr_visual_words": visual,
                "pdf_embedded_words": embedded,
                "spatial": spatial,
                "a08_line_baseline_review_items": baseline_count,
                "a08_line_baseline": baseline,
            })
    return {
        "experiment": "A10",
        "method": "spatial word matching OCR TSV vs PyMuPDF words",
        "cases": rows,
        "total_spatial_review_items": sum(
            row["spatial"]["review_items"] for row in rows
        ),
        "total_baseline_review_items": sum(
            row["a08_line_baseline_review_items"] for row in rows
        ),
        "limitations": [
            "OCR errors can create differences in legitimate documents.",
            "Greedy nearest word matching is not a reliable table-cell parser.",
            "No automatic attack classification or deletion.",
            "All datasets synthetic; thresholds exploratory.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="A10: OCR espacial e palavras embutidas")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--language", default="eng")
    parser.add_argument("--similarity", type=float, default=0.76)
    parser.add_argument("--max-distance", type=float, default=19)
    args = parser.parse_args()
    if not 0 < args.similarity <= 1 or args.max_distance <= 0:
        parser.error("Parâmetros inválidos")
    report = evaluate(
        args.output_dir, language=args.language, executable=args.tesseract,
        similarity=args.similarity, max_distance=args.max_distance,
    )
    output = args.output_dir / "a10_report.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for case in report["cases"]:
        print(
            f"{case['case_id']}: A08={case['a08_line_baseline_review_items']}, "
            f"A10={case['spatial']['review_items']}"
        )
    print("Relatório:", output)


if __name__ == "__main__":
    main()
