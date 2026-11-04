"""A08: OCR sobre pixels renderizados vs extração textual do PDF, sem Gemini."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from difflib import SequenceMatcher
from pathlib import Path

import fitz

from experiments.pdf_representation.a07_correspondence import make_fixture

DEFAULT_DIR = Path("data/executions/pdf_representation/a08")


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def compare_ocr_to_extracted(
    ocr_lines: list[str], extracted_lines: list[str], threshold: float = 0.86
) -> dict:
    """Alinhamento monotônico; preserva substituições aproximadas e linhas sem par."""
    visual = [s for s in ocr_lines if normalize(s)]
    extracted = [s for s in extracted_lines if normalize(s)]
    n, m = len(visual), len(extracted)
    scores = [
        [
            SequenceMatcher(None, normalize(a), normalize(b), autojunk=False).ratio()
            for b in extracted
        ]
        for a in visual
    ]
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    actions = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = dp[i - 1][j]
            actions[i][j] = "skip_ocr"
            if dp[i][j - 1] > dp[i][j]:
                dp[i][j] = dp[i][j - 1]
                actions[i][j] = "skip_extracted"
            score = scores[i - 1][j - 1]
            if score >= threshold and dp[i - 1][j - 1] + score > dp[i][j]:
                dp[i][j] = dp[i - 1][j - 1] + score
                actions[i][j] = "match"
    matched = []
    i, j = n, m
    while i and j:
        if actions[i][j] == "match":
            matched.append((i - 1, j - 1, round(scores[i - 1][j - 1], 4)))
            i -= 1
            j -= 1
        elif actions[i][j] == "skip_extracted":
            j -= 1
        else:
            i -= 1
    matched.reverse()
    seen_visual = {i for i, _, _ in matched}
    seen_extracted = {j for _, j, _ in matched}
    approximate = [
        {
            "ocr_line": i + 1, "extracted_line": j + 1,
            "ocr_text": visual[i], "extracted_text": extracted[j],
            "similarity": score, "requires_review": True,
        }
        for i, j, score in matched
        if normalize(visual[i]) != normalize(extracted[j])
    ]
    return {
        "matched_count": len(matched),
        "approximate_matches": approximate,
        "unmatched_extracted": [
            {"line_number": j + 1, "text": extracted[j], "requires_review": True}
            for j in range(m) if j not in seen_extracted
        ],
        "unmatched_ocr": [
            {"line_number": i + 1, "text": visual[i], "requires_review": True}
            for i in range(n) if i not in seen_visual
        ],
        "coverage_of_extracted_lines": round(len(matched) / m, 4) if m else None,
        "threshold": threshold,
    }


def run_ocr(
    page: fitz.Page, *, scale: float = 2.0,
    language: str = "eng", executable: str = "tesseract",
) -> dict:
    if shutil.which(executable) is None and not Path(executable).exists():
        raise RuntimeError(
            f"Tesseract não encontrado: {executable}. "
            "Instale o programa ou indique o caminho usando --tesseract."
        )
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    command = [executable, "stdin", "stdout", "--psm", "6", "-l", language]
    try:
        result = subprocess.run(
            command, input=pix.tobytes("png"), capture_output=True,
            timeout=60, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Tempo limite de OCR excedido") from exc
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace")[:1000]
        raise RuntimeError(f"Tesseract falhou ({result.returncode}): {detail}")
    raw = result.stdout.decode("utf-8", errors="replace")
    return {
        "text": raw,
        "lines": [line.strip() for line in raw.splitlines() if line.strip()],
        "render_width": pix.width,
        "render_height": pix.height,
        "render_sha256": hashlib.sha256(pix.samples).hexdigest(),
    }


def analyze(
    paths: dict[str, Path], *, scale: float = 2.0,
    language: str = "eng", executable: str = "tesseract",
    threshold: float = 0.86,
) -> dict:
    conditions = []
    for case_id, path in paths.items():
        with fitz.open(path) as pdf:
            if pdf.page_count != 1:
                raise ValueError("A08 inicial suporta PDFs sintéticos de uma página")
            page = pdf[0]
            visual = run_ocr(
                page, scale=scale, language=language, executable=executable
            )
            extracted = [
                line.strip() for line in page.get_text("text").splitlines()
                if line.strip()
            ]
            comparison = compare_ocr_to_extracted(
                visual["lines"], extracted, threshold=threshold
            )
            conditions.append({
                "case_id": case_id,
                "file_path": str(path),
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "ocr_visual": visual,
                "pdf_extracted_lines": extracted,
                "invisible_spans": sum(
                    span.get("type") == 3 for span in page.get_texttrace()
                ),
                "comparison": comparison,
            })
    render_hashes = [
        c["ocr_visual"]["render_sha256"] for c in conditions
    ]
    return {
        "experiment": "A08",
        "method": "Tesseract sobre pixels vs PyMuPDF get_text(text)",
        "visual_parity_all": len(set(render_hashes)) == 1,
        "conditions": conditions,
        "config": {
            "scale": scale, "language": language, "threshold": threshold
        },
        "limitations": [
            "OCR independente pode errar, omitir ou reordenar conteúdo legítimo.",
            "Texto extraído sem par é um sinal para revisão, não classificação de ataque.",
            "Alinhamento por linhas não é robusto para tabelas, colunas ou texto reordenado.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A08: OCR visual independente vs texto estrutural"
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument("--threshold", type=float, default=0.86)
    args = parser.parse_args()
    if args.scale <= 0 or not 0 < args.threshold <= 1:
        parser.error("Escala > 0 e threshold entre 0 (exclusivo) e 1")
    paths = make_fixture(args.output_dir)
    report = analyze(
        paths, scale=args.scale, language=args.language,
        executable=args.tesseract, threshold=args.threshold,
    )
    output = args.output_dir / "a08_report.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for row in report["conditions"]:
        comparison = row["comparison"]
        print(
            f"{row['case_id']}: pares={comparison['matched_count']}, "
            f"linhas_extras={len(comparison['unmatched_extracted'])}, "
            f"pares_aproximados={len(comparison['approximate_matches'])}, "
            f"ocr_sem_par={len(comparison['unmatched_ocr'])}"
        )
    print("Paridade visual:", report["visual_parity_all"])
    print("Relatório:", output)


if __name__ == "__main__":
    main()
