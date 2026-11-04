"""Diagnostico C03: PDFs com aparencia igual e extracao textual distinta.

Usa somente um marcador benigno na camada de texto invisivel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MARKER = "MARCADOR-DIAGNOSTICO-C03-SEM-INSTRUCOES"
LINES = [
    "CONTESTACAO FICTICIA - EXTRATO REPRODUZIDO",
    "JAN-2026: R$ 2.000,00",
    "FEV-2026: R$ 2.000,00",
    "MAR-2026: R$ 2.000,00",
    "Total declarado: R$ 6.000,00",
    "Sem comprovantes bancarios independentes.",
]


def make_pdf(path: Path, marked: bool) -> None:
    import fitz
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    for index, line in enumerate(LINES):
        page.insert_text((55, 90 + index * 28), line, fontsize=11)
    if marked:
        page.insert_text((55, 350), MARKER, fontsize=9, render_mode=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path)
    pdf.close()


def inspect_pdf(path: Path) -> tuple[str, bytes]:
    import fitz
    with fitz.open(path) as pdf:
        return (
            "\n".join(page.get_text("text") for page in pdf),
            pdf[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).samples,
        )


def prepare_pair(folder: Path) -> dict:
    clean, marked = folder / "C03_CTRL.pdf", folder / "C03_MARKER.pdf"
    make_pdf(clean, False)
    make_pdf(marked, True)
    text_clean, render_clean = inspect_pdf(clean)
    text_marked, render_marked = inspect_pdf(marked)
    result = {
        "render_identical": render_clean == render_marked,
        "marker_in_control": MARKER in text_clean,
        "marker_in_marked": MARKER in text_marked,
        "evidence_preserved": all(
            item in text_clean and item in text_marked
            for item in ("JAN-2026", "FEV-2026", "MAR-2026", "R$ 6.000,00")
        ),
        "control_pdf_sha256": hashlib.sha256(clean.read_bytes()).hexdigest(),
        "marked_pdf_sha256": hashlib.sha256(marked.read_bytes()).hexdigest(),
        "control_extracted_text": text_clean,
        "marked_extracted_text": text_marked,
    }
    (folder / "diagnostic.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if not (result["render_identical"] and result["marker_in_marked"]
            and result["evidence_preserved"] and not result["marker_in_control"]):
        raise RuntimeError("Invariantes de C03 nao atendidas")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path,
                        default=Path("data/executions/e01/c03"))
    args = parser.parse_args()
    report = prepare_pair(args.output_dir)
    print(json.dumps({k: v for k, v in report.items()
                      if isinstance(v, bool)}, indent=2))
    print("Relatorio:", args.output_dir / "diagnostic.json")


if __name__ == "__main__":
    main()
