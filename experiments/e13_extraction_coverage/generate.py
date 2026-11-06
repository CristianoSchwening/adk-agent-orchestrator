"""Corpus E13 inteiramente fictício; referência conhecida não é sensor."""
from __future__ import annotations

from pathlib import Path

CASES = (
    "text_control", "raster_page", "mixed_page", "vector_table",
    "opaque_overlay", "white_on_white", "blank_page",
)
BASE_FACT = "PETICAO FICTICIA P-013: valor alegado R$ 1.500,00."
IMAGE_FACT = "ANEXO VISUAL: segundo lancamento alegado R$ 200,00."
TABLE_FACT = "TABELA VISUAL: valor alegado R$ 300,00."
COVERED_FACT = "TEXTO COBERTO: contestacao da alegacao."
WHITE_FACT = "TEXTO BRANCO: anotacao de diagramacao."


def _image_bytes(text: str) -> bytes:
    import fitz

    with fitz.open() as pdf:
        p = pdf.new_page(width=595, height=160)
        p.insert_text((40, 70), text, fontsize=11)
        return p.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")


def generate(folder: Path) -> dict[str, dict]:
    import fitz

    folder.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for variant in CASES:
        path = folder / f"E13_{variant}.pdf"
        page_facts = [[BASE_FACT]]
        with fitz.open() as pdf:
            page = pdf.new_page(width=595, height=842)
            page.insert_text((45, 70), BASE_FACT, fontsize=11)
            if variant == "raster_page":
                annex = pdf.new_page(width=595, height=842)
                annex.insert_image(
                    fitz.Rect(20, 40, 575, 220), stream=_image_bytes(IMAGE_FACT)
                )
                page_facts.append([IMAGE_FACT])
            elif variant == "mixed_page":
                page.insert_image(
                    fitz.Rect(20, 230, 575, 410), stream=_image_bytes(IMAGE_FACT)
                )
                page_facts[0].append(IMAGE_FACT)
            elif variant == "vector_table":
                for x in (45, 245, 525):
                    page.draw_line((x, 140), (x, 220))
                for y in (140, 180, 220):
                    page.draw_line((45, y), (525, y))
                page.insert_text((55, 167), TABLE_FACT, fontsize=9)
                page_facts[0].append(TABLE_FACT)
            elif variant == "opaque_overlay":
                page.insert_text((45, 190), COVERED_FACT, fontsize=11)
                page.draw_rect(
                    fitz.Rect(40, 170, 530, 206), color=(1, 1, 1),
                    fill=(1, 1, 1), overlay=True,
                )
                page_facts[0].append(COVERED_FACT)
            elif variant == "white_on_white":
                page.insert_text((45, 190), WHITE_FACT, fontsize=11, color=(1, 1, 1))
                page_facts[0].append(WHITE_FACT)
            elif variant == "blank_page":
                pdf.new_page(width=595, height=842)
                page_facts.append([])
            pdf.save(path, garbage=4, deflate=True, no_new_id=True)
        manifest[variant] = {"path": str(path), "expected_facts_by_page": page_facts}
    return manifest
