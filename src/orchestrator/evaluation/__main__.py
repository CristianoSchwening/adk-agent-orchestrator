"""CLI module for Phase 5 deterministic evaluations."""

from __future__ import annotations

import argparse
import json
import sys

from orchestrator.evaluation import evaluate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic orchestrator evaluations.")
    parser.add_argument("dataset", help="Path to an eval dataset JSON file.")
    args = parser.parse_args()

    result = evaluate_dataset(args.dataset)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
