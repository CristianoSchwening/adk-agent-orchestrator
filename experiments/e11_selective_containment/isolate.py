"""E11: extração de projeção visível; não altera PDF original."""
from __future__ import annotations

import hashlib
from pathlib import Path


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def project(path: Path) -> dict:
    import fitz

    with fitz.open(path) as pdf:
        if pdf.page_count != 1:
            raise ValueError("E11 exige PDF sintético de uma página")
        page = pdf[0]
        extracted = page.get_text("text", sort=False)
        visible, isolated = [], []
        for span in page.get_texttrace():
            text = "".join(chr(ch[0]) for ch in span["chars"])
            item = {
                "text": text, "page": 1, "seqno": span["seqno"],
                "bbox": list(span["bbox"]), "render_type": span["type"],
            }
            if span["type"] == 3:
                isolated.append(item)
            elif span["type"] == 0:
                visible.append(item)
            else:
                raise ValueError("Operador não previsto: recusar projeção")
        # Esta ordenação só foi verificada no corpus E08; não é genérica.
        visible.sort(key=lambda x: (round(x["bbox"][1] / 3), x["bbox"][0]))
        safe = "\n".join(x["text"] for x in visible)
        if safe:
            safe += "\n"
        if any(item["text"] in safe for item in isolated):
            raise ValueError("Texto isolado presente na saída")
    return {
        "pdf_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "original_text_sha256": hash_text(extracted),
        "safe_text": safe,
        "safe_text_sha256": hash_text(safe),
        "isolated": isolated,
        "same_as_full_extraction": safe == extracted,
    }
