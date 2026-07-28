"""Versioned structured state used to observe agent deliberation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

JSPACE_SCHEMA_VERSION = "orchestrator.jspace.v1"
LifecyclePhase = Literal[
    "started", "progress", "tool_result", "blocked", "failed", "completed", "violation"
]


class JSpaceValidationError(ValueError):
    """Raised when mandatory agent metadata is missing or invalid."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AgentIdentity:
    name: str
    role: str = "agent"
    workflow: str | None = None


@dataclass(frozen=True)
class Lifecycle:
    phase: LifecyclePhase
    status: str
    iteration: int | None = None


@dataclass(frozen=True)
class PromptCapture:
    system_instruction: str | None = None
    agent_instruction: str | None = None
    session_context: dict[str, Any] = field(default_factory=dict)
    input_messages: list[dict[str, Any]] = field(default_factory=list)
    tool_definitions: list[dict[str, Any]] = field(default_factory=list)
    model_output: str | None = None


@dataclass(frozen=True)
class StructuredDeliberation:
    objective: str
    interpretation: str | None = None
    current_step: str | None = None
    plan: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    criticisms: list[str] = field(default_factory=list)
    next_action: str | None = None

    @classmethod
    def from_mapping(
        cls, value: dict[str, Any], *, objective: str
    ) -> StructuredDeliberation:
        if not isinstance(value, dict):
            raise JSpaceValidationError("jspace metadata must be a JSON object")
        resolved_objective = str(value.get("objective") or objective).strip()
        if not resolved_objective:
            raise JSpaceValidationError("jspace.objective is required")
        return cls(
            objective=resolved_objective,
            interpretation=_optional_text(value.get("interpretation")),
            current_step=_optional_text(value.get("current_step")),
            plan=_object_list(value.get("plan")),
            assumptions=_string_list(value.get("assumptions")),
            hypotheses=_string_list(value.get("hypotheses")),
            evidence=_object_list(value.get("evidence")),
            decisions=_object_list(value.get("decisions")),
            uncertainties=_string_list(value.get("uncertainties")),
            blockers=_string_list(value.get("blockers")),
            criticisms=_string_list(value.get("criticisms")),
            next_action=_optional_text(value.get("next_action")),
        )


@dataclass(frozen=True)
class JSpaceSnapshot:
    session_id: str
    sequence: int
    agent: AgentIdentity
    lifecycle: Lifecycle
    jspace: StructuredDeliberation
    prompt_capture: PromptCapture
    invocation_id: str | None = None
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=utc_now_iso)
    schema_version: str = JSPACE_SCHEMA_VERSION
    execution: dict[str, Any] = field(default_factory=dict)
    causality: dict[str, Any] = field(default_factory=dict)
    integrity: dict[str, Any] = field(
        default_factory=lambda: {
            "redacted": False,
            "validation_status": "valid",
            "reasoning_capture": {
                "type": "structured_deliberation",
                "is_hidden_chain_of_thought": False,
            },
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]
