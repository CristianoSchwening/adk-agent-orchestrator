"""Versioned context intelligence models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from orchestrator.planning.models import utc_now_iso

USER_PROFILE_SCHEMA_VERSION = "orchestrator.user_profile.v1"
CONTEXT_PACKAGE_SCHEMA_VERSION = "orchestrator.context_package.v2"
TASK_CONTEXT_SCHEMA_VERSION = "orchestrator.task_context.v2"


@dataclass(frozen=True)
class UserProfile:
    """Stable, user-owned preferences shared across workstreams."""

    user_id: str
    display_name: str = ""
    role: str = ""
    organization: str = ""
    locale: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"
    expertise: list[str] = field(default_factory=list)
    preferences: dict[str, str] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    schema_version: str = USER_PROFILE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> UserProfile:
        return cls(
            user_id=str(value["user_id"]).strip(),
            display_name=str(value.get("display_name") or "").strip(),
            role=str(value.get("role") or "").strip(),
            organization=str(value.get("organization") or "").strip(),
            locale=str(value.get("locale") or "pt-BR").strip(),
            timezone=str(value.get("timezone") or "America/Sao_Paulo").strip(),
            expertise=[str(item) for item in value.get("expertise", [])],
            preferences={
                str(key): str(item) for key, item in value.get("preferences", {}).items()
            },
            constraints=[str(item) for item in value.get("constraints", [])],
            schema_version=str(value.get("schema_version") or USER_PROFILE_SCHEMA_VERSION),
        )


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
    user_profile: UserProfile | None = None
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
            user_profile=(
                UserProfile.from_dict(value["user_profile"])
                if isinstance(value.get("user_profile"), dict)
                else None
            ),
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
    user_profile: UserProfile | None
    constraints: list[str]
    entities: list[ContextEntity]
    terminology: dict[str, str]
    contextual_tools: list[str]
    dependency_results: dict[str, Any]
    schema_version: str = TASK_CONTEXT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
