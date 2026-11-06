"""Comando E12 para gerar PDFs e relatório sem Gemini."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .diagnostic import FOLDER, OUTPUT, run


def main() -> None:
    parser = argparse.ArgumentParser(description="E12: visibilidade PDF")
    parser.add_argument("--folder", type=Path, default=FOLDER)
    parser.add_argument("--report", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = run(args.folder)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for variant, data in result["cases"].items():
        print(variant, data["signals"], "revisao=", data["human_review_required"])
    print("Relatório:", args.report)


if __name__ == "__main__":
    main()
