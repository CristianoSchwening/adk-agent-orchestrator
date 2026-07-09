"""Loop 3 — Event-Driven: cron scheduler + webhook trigger + execution history."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from orchestrator.contracts.dto import utc_now_iso

TriggerSource = Literal["cron", "webhook", "manual"]
RunStatus = Literal["running", "completed", "failed"]


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class ScheduleConfig:
    objective: str
    workflow: str
    interval_seconds: int
    active: bool
    created_at: str = field(default_factory=utc_now_iso)
    next_run_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionSummary:
    run_id: str
    objective: str
    workflow: str
    source: TriggerSource
    status: RunStatus
    started_at: str
    finished_at: str
    duration_ms: int
    response_count: int
    verification_passed: bool | None = None
    verification_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── EventLoop singleton ────────────────────────────────────────────────────────

class EventLoop:
    """
    Loop 3 — Event-Driven.

    Provides:
    • Webhook trigger  — POST /api/loop3/webhook/{token}
    • Cron scheduler   — configurable interval, runs demo in background
    • Execution history — last N runs with source, status, duration
    """

    def __init__(self, max_history: int = 20) -> None:
        self.max_history = max_history
        self.history: list[ExecutionSummary] = []
        self.schedule: ScheduleConfig | None = None
        self.webhook_token: str = uuid.uuid4().hex[:12]
        self._cron_task: asyncio.Task | None = None
        # injected by server at startup
        self._demo_runner: Any = None

    # ── Config ────────────────────────────────────────────────────────────────

    def set_demo_runner(self, runner: Any) -> None:
        """Inject the demo runner callable (to avoid circular imports)."""
        self._demo_runner = runner

    # ── Schedule management ───────────────────────────────────────────────────

    def configure_schedule(
        self,
        objective: str,
        workflow: str,
        interval_seconds: int,
        active: bool,
    ) -> ScheduleConfig:
        """Set or update cron schedule configuration."""
        if self._cron_task and not self._cron_task.done():
            self._cron_task.cancel()
            self._cron_task = None

        cfg = ScheduleConfig(
            objective=objective,
            workflow=workflow,
            interval_seconds=max(10, interval_seconds),
            active=active,
        )
        self.schedule = cfg

        if active:
            self._cron_task = asyncio.create_task(
                self._cron_loop(objective, workflow, cfg.interval_seconds)
            )
            cfg.next_run_at = _seconds_from_now(cfg.interval_seconds)

        return cfg

    def stop_schedule(self) -> None:
        if self._cron_task and not self._cron_task.done():
            self._cron_task.cancel()
            self._cron_task = None
        if self.schedule:
            self.schedule.active = False
            self.schedule.next_run_at = None

    # ── Trigger ───────────────────────────────────────────────────────────────

    async def trigger(
        self,
        objective: str,
        workflow: str,
        source: TriggerSource = "webhook",
    ) -> ExecutionSummary:
        """Run the agent (demo) and record the result in history."""
        run_id = uuid.uuid4().hex[:8]
        started = _now_ms()
        started_iso = utc_now_iso()

        try:
            result = await self._demo_runner(objective, workflow)
            finished_ms = _now_ms()
            duration = finished_ms - started

            responses = result.get("progressive_agent_responses", [])
            # detect verification pass from grader metadata
            grader = next(
                (r for r in responses if r.get("agent_role") == "Grader"
                 and r.get("metadata", {}).get("passed") is True),
                None,
            )
            grader_fail = next(
                (r for r in responses if r.get("agent_role") == "Grader"
                 and r.get("metadata", {}).get("passed") is False),
                None,
            )
            v_passed: bool | None = None
            v_score: float | None = None
            if grader:
                v_passed = True
                v_score = grader["metadata"].get("overall_score")
            elif grader_fail:
                v_passed = False
                v_score = grader_fail["metadata"].get("overall_score")

            summary = ExecutionSummary(
                run_id=run_id,
                objective=objective,
                workflow=workflow,
                source=source,
                status="completed",
                started_at=started_iso,
                finished_at=utc_now_iso(),
                duration_ms=duration,
                response_count=len(responses),
                verification_passed=v_passed,
                verification_score=v_score,
            )
        except Exception as exc:
            summary = ExecutionSummary(
                run_id=run_id,
                objective=objective,
                workflow=workflow,
                source=source,
                status="failed",
                started_at=started_iso,
                finished_at=utc_now_iso(),
                duration_ms=_now_ms() - started,
                response_count=0,
            )

        self._record(summary)
        return summary

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _cron_loop(
        self, objective: str, workflow: str, interval: int
    ) -> None:
        """Background task that fires the agent every `interval` seconds."""
        while True:
            try:
                await asyncio.sleep(interval)
                await self.trigger(objective, workflow, source="cron")
                if self.schedule:
                    self.schedule.next_run_at = _seconds_from_now(interval)
            except asyncio.CancelledError:
                break
            except Exception:
                pass  # keep the loop alive even on error

    def _record(self, summary: ExecutionSummary) -> None:
        self.history.insert(0, summary)
        if len(self.history) > self.max_history:
            self.history = self.history[: self.max_history]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _seconds_from_now(seconds: int) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
