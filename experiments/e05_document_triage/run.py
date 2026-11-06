"""Gera relatório offline de demonstração da política E05 (sem Gemini)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.e05_document_triage.fixtures import examples
from experiments.e05_document_triage.policy import decide, result_for_downstream

DEFAULT_REPORT = Path("data/executions/e05/offline_demo.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="E05: demonstração determinística de triagem")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.report.is_dir():
        parser.error("--report deve apontar para um arquivo")
    outputs = []
    for case in examples():
        decision = decide(**case)
        outputs.append(result_for_downstream(decision))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps({
            "experiment": "E05", "mode": "offline_synthetic_fixture",
            "not_real_classifier_predictions": True,
            "cases": outputs,
        }, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for item in outputs:
        print(item["document_id"], item["triage_action"])
    print("Relatório ilustrativo:", args.report)


if __name__ == "__main__":
    main()
