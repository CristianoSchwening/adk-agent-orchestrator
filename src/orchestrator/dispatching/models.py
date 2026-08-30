"""Versioned runtime state for sequential task dispatch."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from orchestrator.planning.models import utc_now_iso

TASK_RUN_SCHEMA_VERSION = "orchestrator.task_run.v2"
TaskRunStatus = Literal["pending", "ready", "assigned", "running", "completed", "failed", "blocked"]
PlanRunStatus = Literal["running", "completed", "failed"]


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PlanRun:
        return cls(
            run_id=str(value["run_id"]),
            plan_id=str(value["plan_id"]),
            status=value["status"],
            tasks=[TaskRun(**task) for task in value.get("tasks", [])],
            created_at=str(value.get("created_at") or utc_now_iso()),
            updated_at=str(value.get("updated_at") or utc_now_iso()),
            schema_version=str(value.get("schema_version") or TASK_RUN_SCHEMA_VERSION),
        )
