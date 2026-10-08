"""Explicit Kev MCP probe and optional shadow decisions; no model weights required."""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import math
from time import perf_counter
from typing import Any

from orchestrator.config import OrchestratorSettings
from orchestrator.dispatching.dispatcher import AGENT_CAPABILITIES
from orchestrator.mcp.factory import connection_headers


def normalize_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Gradio currently wraps [HTML, response, report] as a Python literal string."""
    blocks = payload.get("content", [])
    text = next((item["text"] for item in blocks if item.get("type") == "text"), "")
    if len(text) > 262_144:
        raise ValueError("Kev response exceeds the parsing limit")
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = ast.literal_eval(text)  # Data only; never execute returned code.
    response = decoded[1] if isinstance(decoded, list) and len(decoded) == 3 else decoded
    answer = response["answers"]["agent"]
    probabilities = answer["probabilities"]
    if answer["choice"] not in AGENT_CAPABILITIES or set(probabilities) != set(AGENT_CAPABILITIES):
        raise ValueError("Kev returned an unknown or incomplete agent selection")
    values = list(probabilities.values())
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError("Invalid Kev probabilities")
    if abs(sum(values) - 1) > 0.01:
        raise ValueError("Kev probabilities do not sum to one")
    confidence = answer.get("confidence")
    if (
        type(confidence) not in (int, float)
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("Invalid Kev confidence")
    return {
        "choice": answer["choice"], "probabilities": probabilities,
        "confidence": confidence, "model": response.get("model"),
        "model_latency_ms": response.get("latency_ms"),
    }


def decision_arguments(state: str) -> dict[str, Any]:
    return {
        "state_text": state,
        "questions_json": json.dumps({
            "agent": {
                "type": "choice",
                "instructions": "Which specialist best matches this task?",
                "criteria": {
                    name: ", ".join(sorted(capabilities))
                    for name, capabilities in AGENT_CAPABILITIES.items()
                },
            }
        }),
        "model_choice": "Kev-4B",
        "calibrated": True,
        "date_facts": False,
        "check_stability": False,
    }


async def query_kev(
    settings: OrchestratorSettings, *, state: str | None = None
) -> dict[str, Any]:
    """Discover only when state is None; otherwise invoke exactly kev_decide.

    The SDK owns transport/session cleanup within the same task. A single bounded
    attempt avoids retries consuming the public Space's GPU quota.
    """
    import anyio
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    server = next((item for item in settings.mcp_servers if item.name == "kev"), None)
    if server is None or server.transport != "streamable_http" or not server.url:
        raise ValueError("Configure a streamable_http MCP server named kev with a URL")
    with anyio.fail_after(60):
        async with streamablehttp_client(
            server.url, headers=connection_headers(server), timeout=15, sse_read_timeout=55
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                names = [tool.name for tool in listing.tools]
                if "kev_decide" not in names:
                    raise ValueError("The configured server does not expose kev_decide")
                if state is None:
                    return {"status": "connected", "tools": names}
                result = await session.call_tool("kev_decide", decision_arguments(state))
                if result.isError:
                    # Do not put upstream errors (potentially echoing inputs) in traces.
                    raise RuntimeError("Kev returned an MCP tool error; check quota/authentication")
                return normalize_response(
                    result.model_dump(mode="json", by_alias=True, exclude_none=True)
                )


async def observe_task(settings: OrchestratorSettings, task: Any) -> dict[str, Any]:
    """Send only task description/capabilities; never changes dispatch selection."""
    started = perf_counter()
    try:
        result = await query_kev(settings, state=json.dumps({
            "title": task.title,
            "description": task.description,
            "required_capabilities": task.required_capabilities,
        }, ensure_ascii=False))
        observation = {"status": "observed", "response": result}
    except Exception as exc:
        observation = {"status": "unavailable", "error_type": type(exc).__name__}
    return {**observation, "elapsed_ms": round((perf_counter() - started) * 1000)}


def main() -> None:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Send one synthetic research task")
    args = parser.parse_args()
    load_dotenv()
    state = "Find public documentation and supporting sources about agent orchestration."
    try:
        result = asyncio.run(query_kev(
            OrchestratorSettings.from_env(), state=state if args.smoke else None
        ))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
