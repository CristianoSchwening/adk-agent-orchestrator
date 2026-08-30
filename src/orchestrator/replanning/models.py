"""Controlled replanning contracts and history."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from orchestrator.planning.models import utc_now_iso

ReplanTrigger = Literal[
    "task_failed",
    "blocker_detected",
    "assumption_invalidated",
    "objective_changed",
    "acceptance_criteria_failed",
]
ALLOWED_REPLAN_TRIGGERS = frozenset(
    {
        "task_failed",
        "blocker_detected",
        "assumption_invalidated",
        "objective_changed",
        "acceptance_criteria_failed",
    }
)


@dataclass(frozen=True)
class ReplanRequest:
    trigger: ReplanTrigger
    rationale: str
    task_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    requested_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.trigger not in ALLOWED_REPLAN_TRIGGERS:
            raise ValueError(f"unsupported replan trigger: {self.trigger}")
        if not self.rationale.strip():
            raise ValueError("replan rationale must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
