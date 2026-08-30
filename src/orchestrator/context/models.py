"""Versioned context intelligence models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from orchestrator.planning.models import utc_now_iso

CONTEXT_PACKAGE_SCHEMA_VERSION = "orchestrator.context_package.v1"
TASK_CONTEXT_SCHEMA_VERSION = "orchestrator.task_context.v1"


@dataclass(frozen=True)
class Workstream:
    workstream_id: str
    name: str
    summary: str


@dataclass(frozen=True)
class ContextEntity:
    entity_id: str
    name: str
    entity_type: str
    description: str
    aliases: list[str] = field(default_factory=list)
    related_capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextPackage:
    context_id: str
    objective: str
    workstream: Workstream
    entities: list[ContextEntity] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    terminology: dict[str, str] = field(default_factory=dict)
    tool_categories: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    schema_version: str = CONTEXT_PACKAGE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ContextPackage:
        return cls(
            context_id=str(value["context_id"]),
            objective=str(value["objective"]),
            workstream=Workstream(**value["workstream"]),
            entities=[ContextEntity(**item) for item in value.get("entities", [])],
            constraints=[str(item) for item in value.get("constraints", [])],
            terminology={str(key): str(item) for key, item in value.get("terminology", {}).items()},
            tool_categories=[str(item) for item in value.get("tool_categories", [])],
            created_at=str(value.get("created_at") or utc_now_iso()),
            schema_version=str(value.get("schema_version") or CONTEXT_PACKAGE_SCHEMA_VERSION),
        )


@dataclass(frozen=True)
class TaskContext:
    task_id: str
    workstream_id: str
    objective: str
    constraints: list[str]
    entities: list[ContextEntity]
    terminology: dict[str, str]
    contextual_tools: list[str]
    dependency_results: dict[str, Any]
    schema_version: str = TASK_CONTEXT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
