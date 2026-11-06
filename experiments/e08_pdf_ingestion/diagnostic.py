"""Sinais técnicos verificáveis; não infere intenção maliciosa ou OCR."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(path: Path) -> dict:
    import fitz

    if not path.is_file():
        raise FileNotFoundError(path)
    pages = []
    with fitz.open(path) as doc:
        if not doc.page_count:
            raise ValueError("PDF sem páginas")
        for number, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=False)
            invisible = sum(
                entry[0] == "ignore-text" for entry in page.get_bboxlog()
            )
            images = len(page.get_images(full=True))
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            signals = []
            if invisible:
                signals.append("non_rendered_text_operation")
            if images and not text.strip():
                signals.append("image_only_without_extracted_text")
            pages.append({
                "page": number,
                "extracted_text": text,
                "text_sha256": sha(text.encode("utf-8")),
                "render_sha256": sha(pix.samples),
                "extracted_characters": len(text),
                "non_rendered_text_operations": invisible,
                "embedded_image_count": images,
                "signals": signals,
            })
    return {
        "path": str(path),
        "pdf_sha256": sha(path.read_bytes()),
        "page_count": len(pages),
        "pages": pages,
        "signals": sorted({signal for p in pages for signal in p["signals"]}),
        "ingestion_anomaly": any(page["signals"] for page in pages),
    }
