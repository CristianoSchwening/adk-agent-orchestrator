"""E12: audita operações e sinaliza casos suspeitos; não sanitiza PDF.

A heurística de cor SOMENTE vale neste corpus que tem fundo branco
conhecido e sem objetos/oclusões. Em PDFs arbitrários, o fundo efetivo,
transparência, imagens e camadas exigem análise adicional.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .generate import FACTS, VARIANTS, generate

OUTPUT = Path("data/executions/e12/visibility_report.json")
FOLDER = Path("data/experiments/e12")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(path: Path) -> dict:
    import fitz

    all_spans, signals, pages = [], set(), []
    with fitz.open(path) as pdf:
        for page_number, page in enumerate(pdf, 1):
            text = page.get_text("text", sort=False)
            spans = []
            for span in page.get_texttrace():
                string = "".join(chr(codepoint) for codepoint, *_ in span["chars"])
                if not string.strip():
                    continue
                color = tuple(float(v) for v in span["color"])
                is_unrendered = span["type"] == 3
                is_white_on_white = (
                    span["type"] == 0 and len(color) >= 3
                    and all(channel >= 0.97 for channel in color[:3])
                )
                flags = []
                if is_unrendered:
                    flags.append("non_rendered_text_operation")
                if is_white_on_white:
                    flags.append("low_contrast_on_known_white_background")
                signals.update(flags)
                item = {
                    "page": page_number, "seqno": span["seqno"],
                    "text": string, "render_type": span["type"],
                    "color": list(color),
                    "bbox": [round(x, 3) for x in span["bbox"]],
                    "signals": flags,
                }
                spans.append(item)
                all_spans.append(item)
            if page.get_images(full=True) and not text.strip():
                signals.add("image_without_text_layer")
            pages.append({
                "page": page_number, "extracted_text": text,
                "extracted_sha256": digest(text.encode("utf-8")),
                "image_count": len(page.get_images(full=True)),
                "text_spans": spans,
            })
    isolated = [item for item in all_spans if item["signals"]]
    visible = [item for item in all_spans if not item["signals"]]
    # Projeção para DIAGNÓSTICO, NÃO para alimentar o agente.
    visible_text = "\n".join(item["text"] for item in visible)
    return {
        "pdf_sha256": digest(path.read_bytes()),
        "pages": pages, "signals": sorted(signals),
        "flagged_spans": isolated,
        "diagnostic_projection": visible_text,
        "projection_sha256": digest(visible_text.encode("utf-8")),
        "all_facts_preserved": all(fact in visible_text for fact in FACTS),
        "human_review_required": bool(signals),
        "automatic_release": False,
        "safe_to_send_to_legal_agent": False,
    }


def run(folder: Path = FOLDER) -> dict:
    paths = generate(folder)
    cases = {variant: inspect(path) for variant, path in paths.items()}
    expected = {
        "control": [],
        "render_mode_3": ["non_rendered_text_operation"],
        "white_on_white": ["low_contrast_on_known_white_background"],
        "white_benign": ["low_contrast_on_known_white_background"],
        "quoted_visible": [],
        "image_only": ["image_without_text_layer"],
    }
    checks = {
        key: value["signals"] == expected[key] for key, value in cases.items()
    }
    checks["all_known_facts_preserved"] = all(
        case["all_facts_preserved"] for case in cases.values()
    )
    checks["white_text_is_type_zero"] = any(
        span["render_type"] == 0
        for span in cases["white_on_white"]["flagged_spans"]
    )
    checks["white_benign_also_flagged"] = bool(
        cases["white_benign"]["flagged_spans"]
    )
    checks["visible_quote_not_flagged"] = not cases["quoted_visible"]["signals"]
    if not all(checks.values()):
        raise RuntimeError("Falharam os invariantes sintéticos E12: " + str(checks))
    return {
        "experiment": "E12",
        "mode": "synthetic_tcu_informed_visibility_stress_test",
        "reference": {
            "tcu": "Acórdão 2836/2026 - Plenário, TC 001.458/2026-4",
            "trt8": "ATOrd 0001062-55.2025.5.08.0130",
            "origin": "technical_reconstruction_not_original_court_filing",
        },
        "cases": cases, "checks": checks,
        "observations": {
            "flagged_pdfs": sum(bool(v["signals"]) for v in cases.values()),
            "benign_white_text_flagged": True,
            "real_attack_identification_validated": False,
            "semantic_classifier_executed": False,
            "legal_agent_invoked": False,
        },
        "limitations": [
            "Corpus sintético, não são PDFs do TCU ou TRT.",
            "A cor branca é suspeita apenas sob fundo branco conhecido.",
            "Outras formas de ocultação, camadas e sobreposições não avaliadas.",
            "Texto branco benigno também foi sinalizado: não presumir malícia.",
            "Projeção diagnóstica não foi autorizada como fonte do agente.",
            "Não há OCR, inspeção semântica Gemini, ou contenção em produção.",
        ],
    }
