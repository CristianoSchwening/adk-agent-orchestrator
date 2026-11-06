"""E08: mede PDF e demonstra E07; classificações são fixtures, não Gemini."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.e05_document_triage.fixtures import sample_classification
from experiments.e07_dual_axis.policy import POLICY_SHA256, decide_dual
from experiments.e08_pdf_ingestion.diagnostic import inspect
from experiments.e08_pdf_ingestion.generate import BASE_LINES, HIDDEN, prepare

DEFAULT_REPORT = Path("data/executions/e08/ingestion_report.json")


def run(folder: Path) -> dict:
    paths = prepare(folder)
    diagnostics = {key: inspect(path) for key, path in paths.items()}
    ctrl = diagnostics["control"]["pages"][0]
    hidden = diagnostics["hidden_active"]["pages"][0]
    quote = diagnostics["visible_quoted"]["pages"][0]
    image = diagnostics["image_only"]["pages"][0]
    invariants = {
        "hidden_render_equals_control": (
            hidden["render_sha256"] == ctrl["render_sha256"]
        ),
        "hidden_extracted_text_differs": (
            hidden["text_sha256"] != ctrl["text_sha256"]
        ),
        "non_rendered_text_detected": (
            hidden["non_rendered_text_operations"] > 0
            and HIDDEN in hidden["extracted_text"]
        ),
        "control_has_no_invisible_text": (
            ctrl["non_rendered_text_operations"] == 0
        ),
        "quoted_visible_and_extracted": (
            quote["render_sha256"] != ctrl["render_sha256"]
            and "auditoria cita" in quote["extracted_text"]
        ),
        "raster_has_image_but_no_extracted_text": (
            image["embedded_image_count"] > 0
            and not image["extracted_text"].strip()
        ),
        "facts_preserved_in_textual_variants": all(
            all(line in diagnostics[variant]["pages"][0]["extracted_text"]
                for line in BASE_LINES)
            for variant in ("control", "hidden_active", "visible_quoted")
        ),
        "signals_match_expected_variants": (
            not diagnostics["control"]["signals"]
            and not diagnostics["visible_quoted"]["signals"]
            and diagnostics["hidden_active"]["signals"]
            == ["non_rendered_text_operation"]
            and diagnostics["image_only"]["signals"]
            == ["image_only_without_extracted_text"]
        ),
    }
    if not all(invariants.values()):
        raise RuntimeError(f"Invariantes E08 falharam: {invariants}")
    routing = {}
    for variant, detail in diagnostics.items():
        text = detail["pages"][0]["extracted_text"]
        # Somente demonstração sintética; não houve classificação Gemini.
        kind = "quoted" if variant == "visible_quoted" else "legal"
        classification = sample_classification(text, kind) if text.strip() else None
        decision = decide_dual(
            document_id=f"P-008-{variant}",
            excerpt=text if text.strip() else "[SEM TEXTO EXTRAIDO: PDF PRESERVADO]",
            classification=classification,
            context_status="not_provided",
            ingestion_anomaly=detail["ingestion_anomaly"],
        )
        routing[variant] = {
            "classification_mode": "synthetic_fixture_not_gemini",
            "source_pdf": detail["path"],
            "source_pdf_sha256": detail["pdf_sha256"],
            "instruction_disposition": decision.instruction_disposition,
            "human_review_required": decision.human_review_required,
            "review_reasons": list(decision.review_reasons),
            "operational_authority_granted": decision.operational_authority_granted,
        }
    return {
        "experiment": "E08",
        "mode": "offline_pdf_ingestion_diagnostics",
        "ingestion_engine": "PyMuPDF",
        "policy_sha256": POLICY_SHA256,
        "invariants": invariants,
        "diagnostics": diagnostics,
        "policy_demo": routing,
        "limitations": [
            "Texto não renderizado não comprova intenção adversarial.",
            "Paridade visual verificada somente com PyMuPDF.",
            "ignore-text não cobre todas as ocultações possíveis.",
            "PDF rasterizado precisa de OCR; este experimento não faz OCR.",
            "Roteamento usa classificações simuladas, não Gemini.",
            "Marcador de texto ausente não substitui o PDF original.",
            "Não há contenção runtime no agente ADK.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="E08: proveniência PDF")
    parser.add_argument(
        "--folder", type=Path, default=Path("data/experiments/e08")
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = run(args.folder)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for variant, decision in report["policy_demo"].items():
        print(variant, decision["human_review_required"], decision["review_reasons"])
    print("Relatório:", args.report)


if __name__ == "__main__":
    main()
