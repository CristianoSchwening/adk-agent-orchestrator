"""General-purpose, versioned task-plan models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

TASK_PLAN_SCHEMA_VERSION = "orchestrator.task_plan.v1"
TaskPlanStatus = Literal["draft", "validated", "archived"]
PlannedTaskStrategy = Literal[
    "single_agent",
    "sequential",
    "parallel",
    "review_critic",
    "iterative_refinement",
    "human_in_the_loop",
    "verification",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Goal:
    """Normalized user goal that anchors a task plan."""

    objective: str
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Deliverable:
    """A concrete outcome the completed plan must produce."""

    deliverable_id: str
    description: str


@dataclass(frozen=True)
class PlannedTask:
    """A domain-neutral unit of planned work."""

    task_id: str
    title: str
    description: str
    task_type: str
    depends_on: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    strategy: PlannedTaskStrategy = "single_agent"
    requires_review: bool = False
    requires_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskPlan:
    """Immutable intent describing tasks, dependencies and deliverables."""

    plan_id: str
    goal: Goal
    tasks: list[PlannedTask]
    deliverables: list[Deliverable]
    status: TaskPlanStatus = "draft"
    assumptions: list[str] = field(default_factory=list)
    workstream_id: str | None = None
    revision: int = 1
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: str = TASK_PLAN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TaskPlan:
        goal = value.get("goal") or {}
        return cls(
            plan_id=str(value.get("plan_id") or ""),
            goal=Goal(
                objective=str(goal.get("objective") or ""),
                constraints=[str(item) for item in goal.get("constraints") or []],
                success_criteria=[str(item) for item in goal.get("success_criteria") or []],
            ),
            tasks=[PlannedTask(**item) for item in value.get("tasks") or []],
            deliverables=[Deliverable(**item) for item in value.get("deliverables") or []],
            status=value.get("status", "draft"),
            assumptions=[str(item) for item in value.get("assumptions") or []],
            workstream_id=value.get("workstream_id"),
            revision=int(value.get("revision", 1)),
            created_at=str(value.get("created_at") or utc_now_iso()),
            updated_at=str(value.get("updated_at") or utc_now_iso()),
            schema_version=str(value.get("schema_version") or TASK_PLAN_SCHEMA_VERSION),
        )
