"""A01: auditoria somente-leitura de divergências entre renderização e extração de PDF.

Uso (na raiz do repositório):
python -m experiments.pdf_representation.analyze --control ... --candidate ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT = Path("data/executions/pdf_representation/a01_report.json")
REQUIRED_EVIDENCE = ("JAN-2026", "FEV-2026", "MAR-2026", "R$ 6.000,00")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _span_text(span: dict[str, Any]) -> str:
    """Reconstrói Unicode dos caracteres sem instruir o agente ou filtrar conteúdo."""
    chars = span.get("chars") or ()
    return "".join(
        chr(char[0])
        for char in chars
        if char and isinstance(char[0], int) and 0 <= char[0] <= 0x10FFFF
    )


def _bbox(span: dict[str, Any]) -> list[float]:
    return [round(float(v), 3) for v in span.get("bbox", ())]


def analyze_pdf(path: Path, scale: float = 1.5) -> dict[str, Any]:
    """Lê o PDF sem modificá-lo; registra texto integral e proveniência por span."""
    import fitz

    if not path.is_file():
        raise FileNotFoundError(f"PDF não encontrado: {path}")
    file_hash = _sha256(path.read_bytes())
    pages = []
    with fitz.open(path) as pdf:
        if pdf.page_count == 0:
            raise ValueError(f"PDF sem páginas: {path}")
        for number, page in enumerate(pdf, start=1):
            extracted = page.get_text("text")
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image_signature = {
                "width": pix.width,
                "height": pix.height,
                "channels": pix.n,
                "samples_sha256": _sha256(pix.samples),
            }
            spans = []
            for span in page.get_texttrace():
                mode = span.get("type")
                opacity = span.get("opacity")
                signals = []
                if mode == 3:
                    signals.append("text_render_mode_3")
                if opacity is not None and float(opacity) == 0:
                    signals.append("zero_opacity")
                if signals:
                    spans.append({
                        "page": number,
                        "text": _span_text(span),
                        "bbox": _bbox(span),
                        "text_type": mode,
                        "opacity": opacity,
                        "layer": span.get("layer"),
                        "seqno": span.get("seqno"),
                        "signals": signals,
                    })
            paint_log = page.get_bboxlog(layers=True)
            paint_kinds = {}
            for entry in paint_log:
                kind = entry[0]
                paint_kinds[kind] = paint_kinds.get(kind, 0) + 1
            pages.append({
                "number": number,
                "page_rect": list(page.rect),
                "extracted_text": extracted,
                "text_sha256": _sha256(extracted.encode("utf-8")),
                "render": image_signature,
                "flagged_spans": spans,
                "painting_kinds": paint_kinds,
            })
    return {
        "path": str(path),
        "file_sha256": file_hash,
        "page_count": len(pages),
        "pages": pages,
    }


def compare_reports(control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Compara pixels, texto extraído e manutenção de marcadores factuais."""
    control_pages = control["pages"]
    candidate_pages = candidate["pages"]
    same_count = len(control_pages) == len(candidate_pages)
    rendered_equal = same_count and all(
        left["render"] == right["render"]
        for left, right in zip(control_pages, candidate_pages)
    )
    text_equal = same_count and all(
        left["extracted_text"] == right["extracted_text"]
        for left, right in zip(control_pages, candidate_pages)
    )
    c_text = "\n".join(page["extracted_text"] for page in control_pages)
    a_text = "\n".join(page["extracted_text"] for page in candidate_pages)
    evidence = {
        marker: {"control": marker in c_text, "candidate": marker in a_text}
        for marker in REQUIRED_EVIDENCE
    }
    flagged = [span for page in candidate_pages for span in page["flagged_spans"]]
    return {
        "same_page_count": same_count,
        "visual_parity": rendered_equal,
        "extraction_difference": not text_equal,
        "candidate_flagged_spans": len(flagged),
        "candidate_hidden_text_present": any(span["text"].strip() for span in flagged),
        "evidence_markers": evidence,
        "legitimate_content_preserved": all(
            row["control"] and row["candidate"] for row in evidence.values()
        ),
        "classification": "anomalia_de_representacao_nao_prova_ataque",
    }


def build_report(control_path: Path, candidate_path: Path, scale: float = 1.5) -> dict:
    import fitz

    control = analyze_pdf(control_path, scale)
    candidate = analyze_pdf(candidate_path, scale)
    return {
        "experiment": "A01",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "pymupdf_version": fitz.VersionBind,
        "render_scale": scale,
        "control": control,
        "candidate": candidate,
        "comparison": compare_reports(control, candidate),
        "limitations": [
            "Sinal de invisibilidade não significa ataque malicioso.",
            "A comparação visual depende do motor de renderização e da escala escolhida.",
            "O diagnóstico não remove, filtra ou modifica conteúdo do PDF.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A01: inspecionar PDFs sem alterar arquivos")
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scale", type=float, default=1.5)
    args = parser.parse_args()
    if args.scale <= 0:
        parser.error("--scale deve ser positivo")
    report = build_report(args.control, args.candidate, args.scale)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Paridade visual:", report["comparison"]["visual_parity"])
    print("Extração diferente:", report["comparison"]["extraction_difference"])
    print("Spans sinalizados:", report["comparison"]["candidate_flagged_spans"])
    print("Evidências preservadas:", report["comparison"]["legitimate_content_preserved"])
    print("Relatório:", args.output)


if __name__ == "__main__":
    main()
