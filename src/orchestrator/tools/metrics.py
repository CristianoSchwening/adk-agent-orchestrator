"""In-memory tool usage events and metrics for local ADK tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class ToolUsageEvent:
    """Structured event emitted whenever a local tool wrapper finishes."""

    tool_name: str
    status: str
    elapsed_ms: int
    started_at: str
    finished_at: str
    error_code: str | None = None


class ToolMetricsRecorder:
    """Small process-local metrics recorder for Phase 3 tool observability.

    This intentionally stays simple and dependency-free. Future phases can map
    these events to ADK session events, Cloud Logging, or contract DTOs.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: list[ToolUsageEvent] = []

    def record(
        self,
        *,
        tool_name: str,
        status: str,
        elapsed_ms: int,
        started_at: datetime,
        finished_at: datetime,
        error_code: str | None = None,
    ) -> None:
        event = ToolUsageEvent(
            tool_name=tool_name,
            status=status,
            elapsed_ms=elapsed_ms,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            error_code=error_code,
        )
        with self._lock:
            self._events.append(event)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)

        by_tool: dict[str, dict[str, Any]] = {}
        for event in events:
            bucket = by_tool.setdefault(
                event.tool_name,
                {"calls": 0, "successes": 0, "errors": 0, "timeouts": 0, "total_ms": 0},
            )
            bucket["calls"] += 1
            bucket["total_ms"] += event.elapsed_ms
            if event.status == "success":
                bucket["successes"] += 1
            elif event.error_code == "timeout":
                bucket["timeouts"] += 1
            else:
                bucket["errors"] += 1

        for bucket in by_tool.values():
            bucket["avg_ms"] = round(bucket["total_ms"] / bucket["calls"], 2)

        return {
            "total_calls": len(events),
            "by_tool": by_tool,
            "events": [asdict(event) for event in events],
        }

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


TOOL_METRICS = ToolMetricsRecorder()


def get_tool_usage_metrics() -> dict[str, Any]:
    """Return a serializable snapshot of local tool usage metrics."""

    return TOOL_METRICS.snapshot()


def reset_tool_usage_metrics() -> dict[str, Any]:
    """Clear process-local tool usage metrics and return a status payload."""

    TOOL_METRICS.reset()
    return {"status": "reset", "reset_at": datetime.now(timezone.utc).isoformat()}
