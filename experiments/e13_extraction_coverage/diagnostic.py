"""Sinais mecânicos de ingestão PDF; nenhum percentual de completude."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _overlap(a: tuple, b: tuple) -> bool:
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def inspect(path: Path) -> dict:
    import fitz

    pages = []
    with fitz.open(path) as pdf:
        if not pdf.page_count:
            raise ValueError("PDF sem paginas")
        for number, page in enumerate(pdf, 1):
            text = page.get_text("text", sort=False)
            log = page.get_bboxlog()
            images = len(page.get_images(full=True))
            drawings = len(page.get_drawings())
            traces = page.get_texttrace()
            signals = set()
            if images:
                signals.add("image_region_unassessed_without_ocr")
                if not text.strip():
                    signals.add("image_page_without_extractable_text")
            if drawings:
                signals.add("vector_content_not_semantically_verified")
            if not text.strip() and not images and not drawings:
                signals.add("empty_page_content_unverified")
            if any(span["type"] == 3 for span in traces):
                signals.add("non_rendered_text_operation")
            if any(
                span["type"] == 0 and len(span["color"]) >= 3
                and all(c >= 0.97 for c in span["color"][:3])
                for span in traces
            ):
                signals.add("low_contrast_candidate_white_background_unverified")
            for index, (kind, rect) in enumerate(log):
                if kind == "fill-text" and any(
                    later == "fill-path" and _overlap(rect, later_rect)
                    for later, later_rect in log[index + 1:]
                ):
                    signals.add("possible_later_opaque_occlusion")
                    break
            pages.append({
                "page": number, "extracted_text": text,
                "text_sha256": sha(text.encode("utf-8")),
                "image_count": images, "drawing_count": drawings,
                "signals": sorted(signals),
                "coverage_status": (
                    "requires_review_or_additional_extraction" if signals
                    else "no_mechanical_gap_detected_not_verified_complete"
                ),
            })
    all_signals = sorted({s for p in pages for s in p["signals"]})
    return {
        "pdf_sha256": sha(path.read_bytes()), "page_count": len(pages),
        "pages": pages, "signals": all_signals,
        "security_representation_signals": sorted(s for s in all_signals if s in {
            "non_rendered_text_operation",
            "low_contrast_candidate_white_background_unverified",
            "possible_later_opaque_occlusion",
        }),
        "extraction_coverage_signals": sorted(s for s in all_signals if s in {
            "image_region_unassessed_without_ocr",
            "image_page_without_extractable_text",
            "vector_content_not_semantically_verified",
            "empty_page_content_unverified",
        }),
        "automatic_release": False,
        "safe_for_legal_agent": False,
    }
