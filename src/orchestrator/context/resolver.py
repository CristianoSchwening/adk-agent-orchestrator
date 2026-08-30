"""Build minimal, task-specific context from a broader ContextPackage."""

from __future__ import annotations

from typing import Any

from orchestrator.context.models import ContextEntity, ContextPackage, TaskContext
from orchestrator.planning import PlannedTask
from orchestrator.tools.catalog import TOOL_CATALOG

_CAPABILITY_CATEGORIES = {
    "research": {"http", "documents", "filesystem"},
    "evidence": {"http", "documents"},
    "source_analysis": {"http", "documents"},
    "analysis": {"data", "documents"},
    "data_analysis": {"data"},
    "implementation": {"filesystem", "http", "data"},
    "creation": {"filesystem", "documents"},
    "synthesis": {"model", "documents"},
    "summarization": {"model", "documents"},
    "approval": {"core"},
}


def build_task_context(
    package: ContextPackage,
    task: PlannedTask,
    *,
    dependency_results: dict[str, Any],
    allowed_tool_names: set[str] | None = None,
) -> TaskContext:
    """Return only context relevant to one task and its selected execution node."""

    capabilities = {_normalize(item) for item in task.required_capabilities}
    capabilities.add(_normalize(task.task_type))
    haystack = _tokens(" ".join([task.title, task.description, *task.required_capabilities]))
    entities = [
        entity
        for entity in package.entities
        if _entity_relevant(entity, capabilities=capabilities, haystack=haystack)
    ]
    categories = set(package.tool_categories)
    for capability in capabilities:
        categories.update(_CAPABILITY_CATEGORIES.get(capability, set()))
    tools = [
        tool.name
        for tool in TOOL_CATALOG
        if tool.availability == "available"
        and tool.category in categories
        and (allowed_tool_names is None or tool.name in allowed_tool_names)
    ]
    terminology = {
        term: definition
        for term, definition in package.terminology.items()
        if _tokens(term) & haystack
    }
    return TaskContext(
        task_id=task.task_id,
        workstream_id=package.workstream.workstream_id,
        objective=package.objective,
        constraints=list(package.constraints),
        entities=entities,
        terminology=terminology,
        contextual_tools=tools,
        dependency_results=dependency_results,
    )


def _entity_relevant(
    entity: ContextEntity,
    *,
    capabilities: set[str],
    haystack: set[str],
) -> bool:
    related = {_normalize(item) for item in entity.related_capabilities}
    entity_tokens = _tokens(" ".join([entity.name, entity.description, *entity.aliases]))
    return bool(related & capabilities or entity_tokens & haystack)


def _normalize(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _tokens(value: str) -> set[str]:
    return {token.strip(".,:;()[]{}").lower() for token in value.split() if len(token) > 2}
