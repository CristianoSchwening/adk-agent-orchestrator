"""Runtime helpers shared by local ADK function tools."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from orchestrator.config import OrchestratorSettings
from orchestrator.tools.metrics import TOOL_METRICS


def success_payload(tool_name: str, data: dict[str, Any], *, elapsed_ms: int) -> dict[str, Any]:
    """Build a standard success payload for local tools."""

    return {
        "status": "success",
        "tool_name": tool_name,
        "elapsed_ms": elapsed_ms,
        "data": data,
    }


def error_payload(
    tool_name: str,
    *,
    error_code: str,
    message: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    """Build a standard error payload for local tools."""

    return {
        "status": "error",
        "tool_name": tool_name,
        "elapsed_ms": elapsed_ms,
        "error": {"code": error_code, "message": message},
        "data": {},
    }


def execute_tool_call(
    tool_name: str,
    operation: Callable[[], dict[str, Any]],
    *,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Execute a local tool operation with timeout, errors and metrics."""

    timeout = timeout_seconds or OrchestratorSettings.from_env().tool_timeout_seconds
    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    error_code: str | None = None
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(operation)

    try:
        try:
            data = future.result(timeout=timeout)
            elapsed_ms = int((perf_counter() - started) * 1000)
            return success_payload(tool_name, data, elapsed_ms=elapsed_ms)
        except FutureTimeoutError:
            error_code = "timeout"
            elapsed_ms = int((perf_counter() - started) * 1000)
            future.cancel()
            return error_payload(
                tool_name,
                error_code="timeout",
                message=f"Tool call exceeded {timeout:.2f}s timeout.",
                elapsed_ms=elapsed_ms,
            )
        except Exception as exc:  # noqa: BLE001 - standardize tool-facing errors
            error_code = exc.__class__.__name__
            elapsed_ms = int((perf_counter() - started) * 1000)
            return error_payload(
                tool_name,
                error_code=error_code,
                message=str(exc),
                elapsed_ms=elapsed_ms,
            )
    finally:
        finished_at = datetime.now(timezone.utc)
        elapsed_ms = int((perf_counter() - started) * 1000)
        TOOL_METRICS.record(
            tool_name=tool_name,
            status="success" if error_code is None else "error",
            elapsed_ms=elapsed_ms,
            started_at=started_at,
            finished_at=finished_at,
            error_code=error_code,
        )
        executor.shutdown(wait=False, cancel_futures=True)
