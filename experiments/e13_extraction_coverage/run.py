"""Executa E13 offline com gabarito sintético separado dos sensores."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .diagnostic import inspect
from .generate import CASES, generate

FOLDER = Path("data/experiments/e13")
REPORT = Path("data/executions/e13/coverage_report.json")


def run(folder: Path) -> dict:
    manifest = generate(folder)
    cases = {}
    for variant in CASES:
        doc = manifest[variant]
        diagnostic = inspect(Path(doc["path"]))
        expectations = doc["expected_facts_by_page"]
        assert len(diagnostic["pages"]) == len(expectations)
        benchmark = []
        for page, facts in zip(diagnostic["pages"], expectations):
            benchmark.append({
                "page": page["page"],
                "expected_fact_count": len(facts),
                "missing_in_extraction": [
                    f for f in facts if f not in page["extracted_text"]
                ],
                "found_in_extraction": [
                    f for f in facts if f in page["extracted_text"]
                ],
            })
        cases[variant] = {
            "path": doc["path"], "diagnostic": diagnostic,
            "synthetic_ground_truth_benchmark": benchmark,
        }
    checks = {
        "control_no_anomalies": not cases["text_control"]["diagnostic"]["signals"],
        "raster_missing_known_fact": bool(
            cases["raster_page"]["synthetic_ground_truth_benchmark"][1][
                "missing_in_extraction"
            ]
        ),
        "mixed_missing_known_fact": bool(
            cases["mixed_page"]["synthetic_ground_truth_benchmark"][0][
                "missing_in_extraction"
            ]
        ),
        "vector_grid_separate_from_text": (
            "vector_content_not_semantically_verified"
            in cases["vector_table"]["diagnostic"]["signals"]
            and not cases["vector_table"]["synthetic_ground_truth_benchmark"][0][
                "missing_in_extraction"
            ]
        ),
        "overlay_suspected": (
            "possible_later_opaque_occlusion"
            in cases["opaque_overlay"]["diagnostic"]["signals"]
        ),
        "white_candidate_suspected": (
            "low_contrast_candidate_white_background_unverified"
            in cases["white_on_white"]["diagnostic"]["signals"]
        ),
        "blank_not_inferred_missing_fact": (
            "empty_page_content_unverified"
            in cases["blank_page"]["diagnostic"]["pages"][1]["signals"]
            and not cases["blank_page"]["synthetic_ground_truth_benchmark"][1][
                "missing_in_extraction"
            ]
        ),
        "none_auto_released": all(
            not value["diagnostic"]["automatic_release"] for value in cases.values()
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Falha de invariantes E13: {checks}")
    return {
        "experiment": "E13", "mode": "offline_pdf_coverage_two_axes",
        "cases": cases, "checks": checks,
        "known_synthetic_missing_facts": sum(
            len(page["missing_in_extraction"]) for case in cases.values()
            for page in case["synthetic_ground_truth_benchmark"]
        ),
        "limitations": [
            "O gabarito sintetico nao esta disponivel em PDFs reais.",
            "Ausencia de sinal nao comprova cobertura integral.",
            "Imagens foram marcadas sem OCR; nao se inferiu seu conteudo.",
            "Vetores podem ser meramente decorativos.",
            "Contraste e oclusao sao indicadores candidatos, nao provas visuais.",
            "Nao ha Gemini, liberacao automatica ou contencao runtime.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="E13: integridade da extracao PDF")
    parser.add_argument("--folder", type=Path, default=FOLDER)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    data = run(args.folder)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("E13:", len(data["cases"]), "PDFs; invariantes:", sum(data["checks"].values()))
    print("Relatorio:", args.report)


if __name__ == "__main__":
    main()
