"""Versioned runtime state for sequential task dispatch."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from orchestrator.planning.models import utc_now_iso

TASK_RUN_SCHEMA_VERSION = "orchestrator.task_run.v2"
TaskRunStatus = Literal[
    "pending", "ready", "assigned", "running", "awaiting_human", "completed",
    "failed", "blocked", "cancelled",
]
PlanRunStatus = Literal["running", "awaiting_human", "completed", "failed", "cancelled"]


@dataclass
class TaskRun:
    task_id: str
    status: TaskRunStatus
    assigned_agent: str | None = None
    execution_strategy: str = "single_agent"
    execution_node: str | None = None
    selection_reason: str | None = None
    attempt: int = 0
    result: Any = None
    execution_output: Any = None
    output_status: Literal["not_recorded", "absent", "empty", "present"] = "not_recorded"
    output_recorded_at: str | None = None
    evaluation: dict[str, Any] | None = None
    evaluation_error: str | None = None
    evaluated_at: str | None = None
    kev_observation: dict[str, Any] | None = None
    error: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass
class PlanRun:
    run_id: str
    plan_id: str
    status: PlanRunStatus
    tasks: list[TaskRun]
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: str = TASK_RUN_SCHEMA_VERSION
    parent_run_id: str | None = None
    replan_request: dict[str, Any] | None = None
    terminal_error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PlanRun:
        return cls(
            run_id=str(value["run_id"]),
            parent_run_id=value.get("parent_run_id"),
            replan_request=value.get("replan_request"),
            terminal_error=value.get("terminal_error"),
            plan_id=str(value["plan_id"]),
            status=value["status"],
            tasks=[TaskRun(**task) for task in value.get("tasks", [])],
            created_at=str(value.get("created_at") or utc_now_iso()),
            updated_at=str(value.get("updated_at") or utc_now_iso()),
            schema_version=str(value.get("schema_version") or TASK_RUN_SCHEMA_VERSION),
        )
