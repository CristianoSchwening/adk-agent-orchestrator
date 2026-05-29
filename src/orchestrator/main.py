"""CLI entry point for a single ADK smoke invocation."""

from __future__ import annotations

import argparse
import asyncio

from orchestrator.runner import run_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one ADK orchestrator objective.")
    parser.add_argument("objective", help="Objective to send to the ADK root agent.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    response = asyncio.run(run_once(args.objective))
    print(response)


if __name__ == "__main__":
    main()
