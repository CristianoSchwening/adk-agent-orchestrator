"""Versioned execution contract DTOs for UI/API consumers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

CONTRACT_VERSION = "orchestrator.execution.v1"

TaskStatus = Literal["pending", "running", "completed", "failed", "cancelled", "blocked"]
SubtaskStatus = Literal["pending", "running", "completed", "failed", "skipped", "blocked"]
EventSeverity = Literal["debug", "info", "warning", "error"]


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp for contract DTOs."""

    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class DecisionMetadataDTO:
    """Workflow routing and orchestration decision metadata."""

    selected_workflow: str | None = None
    rationale: str | None = None
    confidence: float | None = None
    alternatives: list[str] = field(default_factory=list)
    policy_version: str | None = None


@dataclass(frozen=True)
class TaskDTO:
    """Top-level task visible to UI/API clients."""

    task_id: str
    objective: str
    status: TaskStatus
    app_name: str
    user_id: str
    session_id: str
    created_at: str
    updated_at: str
    final_response: str | None = None


@dataclass(frozen=True)
class SubtaskDTO:
    """Workflow step/subagent projection for UI timelines."""

    subtask_id: str
    name: str
    status: SubtaskStatus
    agent_name: str | None = None
    workflow: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class EventDTO:
    """Normalized event emitted during task execution."""

    event_id: str
    type: str
    message: str
    timestamp: str
    source: str
    severity: EventSeverity = "info"
    subtask_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactDTO:
    """Artifact reference suitable for frontend rendering or download links."""

    artifact_id: str
    name: str
    mime_type: str | None = None
    uri: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricsDTO:
    """Execution metrics summarized for UI/API clients."""

    duration_ms: int | None
    event_count: int
    subtask_count: int
    artifact_count: int
    tool_call_count: int = 0
    model_event_count: int = 0
    error_count: int = 0
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionContractDTO:
    """Complete versioned execution view consumed by clients."""

    contract_version: str
    task: TaskDTO
    subtasks: list[SubtaskDTO]
    events: list[EventDTO]
    metrics: MetricsDTO
    decision_metadata: DecisionMetadataDTO
    artifacts: list[ArtifactDTO] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the contract into a JSON-compatible dictionary."""

        return asdict(self)
