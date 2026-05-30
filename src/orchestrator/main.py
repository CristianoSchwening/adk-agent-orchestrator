"""CLI entry point for a single ADK smoke invocation."""

from __future__ import annotations

import argparse
import asyncio
import json

from orchestrator.runner import run_once, run_once_contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one ADK orchestrator objective.")
    parser.add_argument("objective", help="Objective to send to the ADK root agent.")
    parser.add_argument(
        "--contract-json",
        action="store_true",
        help="Print the versioned Phase 4 execution contract as JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.contract_json:
        contract = asyncio.run(run_once_contract(args.objective))
        print(json.dumps(contract.to_dict(), ensure_ascii=False, indent=2))
        return

    response = asyncio.run(run_once(args.objective))
    print(response)


if __name__ == "__main__":
    main()
