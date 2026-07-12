"""Map ADK sessions, events and artifacts into the Phase 4 execution contract."""

from __future__ import annotations

import json
from datetime import datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from orchestrator.config import OrchestratorSettings
from orchestrator.contracts import (
    CONTRACT_VERSION,
    AgentVisibleResponse,
    ArtifactDTO,
    DecisionMetadataDTO,
    EventDTO,
    ExecutionContractDTO,
    MetricsDTO,
    SubtaskDTO,
    TaskDTO,
)
from orchestrator.contracts.dto import utc_now_iso

WORKFLOW_STATE_KEYS: dict[str, tuple[str, str]] = {
    "sequential_plan": ("sequential", "plan"),
    "sequential_execution": ("sequential", "execute"),
    "sequential_critique": ("sequential", "critique"),
    "sequential_summary": ("sequential", "summarize"),
    "parallel_plan": ("parallel", "plan"),
    "parallel_research": ("parallel", "research"),
    "parallel_execution": ("parallel", "execute"),
    "parallel_summary": ("parallel", "summarize"),
    "review_candidate": ("review_critic", "author"),
    "review_critique": ("review_critic", "critic"),
    "refinement_draft": ("iterative_refinement", "draft"),
    "refinement_evaluation": ("iterative_refinement", "evaluate"),
    "refinement_result": ("iterative_refinement", "refine"),
    "human_review_context": ("human_in_the_loop", "context"),
    "human_approval_decision": ("human_in_the_loop", "approval"),
    "human_followup": ("human_in_the_loop", "followup"),
    "progressive_response_a": ("progressive_multi_agent_response", "response-a"),
    "progressive_response_b": ("progressive_multi_agent_response", "response-b"),
    "progressive_response_c": ("progressive_multi_agent_response", "response-c"),
    "progressive_agent_responses": ("progressive_multi_agent_response", "publish"),
    "progressive_final_response": ("progressive_multi_agent_response", "finalize"),
    "grader_result": ("loop", "grade"),
}


def map_adk_execution(
    *,
    session: Any,
    events: list[Any],
    objective: str,
    final_response: str,
    settings: OrchestratorSettings | None = None,
    artifacts: list[Any] | dict[str, Any] | None = None,
    task_id: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_ms: int | None = None,
) -> ExecutionContractDTO:
    """Create a UI/API execution contract from ADK runtime outputs.

    The mapper accepts real ADK objects or lightweight fakes/dicts so tests and
    future API layers can validate contract behavior without model credentials.
    """

    resolved_settings = settings or OrchestratorSettings.from_env()
    state = _extract_state(session)
    session_id = _extract_value(session, "id", "session_id") or state.get("session_id") or "unknown"
    app_name = _extract_value(session, "app_name") or resolved_settings.app_name
    user_id = _extract_value(session, "user_id") or resolved_settings.user_id
    now = finished_at or utc_now_iso()
    created_at = started_at or _extract_value(session, "created_at") or now
    status = "completed" if final_response else "running"

    event_dtos = [_map_event(event, index) for index, event in enumerate(events, start=1)]
    artifact_dtos = _map_artifacts(artifacts)
    progressive_responses = _map_progressive_agent_responses(
        state.get("progressive_agent_responses")
    )
    subtasks = _map_subtasks(
        state,
        event_dtos,
        selected_workflow=_selected_workflow(state),
        default_finished_at=now,
    )
    error_count = sum(1 for event in event_dtos if event.severity == "error")
    tool_call_count = sum(1 for event in event_dtos if event.type in {"tool_call", "tool_response"})
    model_event_count = sum(1 for event in event_dtos if event.type in {"model", "final_response"})

    return ExecutionContractDTO(
        contract_version=CONTRACT_VERSION,
        task=TaskDTO(
            task_id=task_id or str(state.get("task_id") or uuid4()),
            objective=objective,
            status="failed" if error_count else status,
            app_name=str(app_name),
            user_id=str(user_id),
            session_id=str(session_id),
            created_at=str(created_at),
            updated_at=now,
            final_response=final_response or None,
        ),
        subtasks=subtasks,
        events=event_dtos,
        metrics=MetricsDTO(
            duration_ms=duration_ms,
            event_count=len(event_dtos),
            subtask_count=len(subtasks),
            artifact_count=len(artifact_dtos),
            tool_call_count=tool_call_count,
            model_event_count=model_event_count,
            error_count=error_count,
            custom={
                "phase": state.get("phase"),
                "tool_timeout_seconds": state.get("tool_timeout_seconds"),
                "mcp_server_count": state.get("mcp_server_count"),
                "progressive_agent_response_count": len(progressive_responses),
                "loop_stop_reason": state.get("loop_stop_reason"),
                "loop_final_score": state.get("loop_final_score"),
                "loop_iterations_used": state.get("loop_iterations_used"),
            },
        ),
        decision_metadata=DecisionMetadataDTO(
            selected_workflow=_selected_workflow(state),
            rationale=_optional_string(state.get("decision_rationale")),
            confidence=_optional_float(state.get("decision_confidence")),
            alternatives=_string_list(state.get("workflow_alternatives")),
            policy_version=_optional_string(state.get("policy_version")),
        ),
        artifacts=artifact_dtos,
        progressive_agent_responses=progressive_responses,
    )


def map_duration_ms(started: float) -> int:
    """Return elapsed milliseconds from a ``perf_counter`` start value."""

    return int((perf_counter() - started) * 1000)


def _extract_state(session: Any) -> dict[str, Any]:
    if isinstance(session, dict):
        raw_state = session.get("state", {})
    else:
        raw_state = getattr(session, "state", {})
    return dict(raw_state or {})


def _extract_value(source: Any, *names: str) -> Any:
    for name in names:
        if isinstance(source, dict) and name in source:
            return source[name]
        if hasattr(source, name):
            return getattr(source, name)
    return None


def _selected_workflow(state: dict[str, Any]) -> str | None:
    workflow = state.get("workflow") or state.get("selected_workflow")
    if workflow:
        return str(workflow)
    for key in WORKFLOW_STATE_KEYS:
        if key in state:
            return WORKFLOW_STATE_KEYS[key][0]
    return None


def _map_event(event: Any, index: int) -> EventDTO:
    event_id = str(_extract_value(event, "id", "event_id") or f"event-{index}")
    author = str(_extract_value(event, "author", "source") or "adk")
    timestamp = _event_timestamp(event)
    content_text = _event_text(event)
    event_type = _event_type(event)
    error = _extract_value(event, "error", "error_message")
    severity = "error" if error else "info"
    message = str(error or content_text or event_type)
    metadata = {
        "invocation_id": _extract_value(event, "invocation_id"),
        "branch": _extract_value(event, "branch"),
    }
    metadata = {key: value for key, value in metadata.items() if value is not None}
    return EventDTO(
        event_id=event_id,
        type=event_type,
        message=message,
        timestamp=timestamp,
        source=author,
        severity=severity,  # type: ignore[arg-type]
        metadata=metadata,
    )


def _event_timestamp(event: Any) -> str:
    timestamp = _extract_value(event, "timestamp", "created_at")
    if isinstance(timestamp, int | float):
        return datetime.fromtimestamp(timestamp).astimezone().isoformat()
    if timestamp:
        return str(timestamp)
    return utc_now_iso()


def _event_type(event: Any) -> str:
    explicit = _extract_value(event, "type", "event_type")
    if explicit:
        return str(explicit)
    if callable(getattr(event, "is_final_response", None)) and event.is_final_response():
        return "final_response"
    if _extract_value(event, "tool_call"):
        return "tool_call"
    if _extract_value(event, "tool_response"):
        return "tool_response"
    if _extract_value(event, "content"):
        return "model"
    return "adk_event"


def _event_text(event: Any) -> str | None:
    text = _extract_value(event, "message", "text")
    if text:
        return str(text)
    content = _extract_value(event, "content")
    parts = _extract_value(content, "parts") if content is not None else None
    if parts:
        return "".join(str(_extract_value(part, "text") or "") for part in parts).strip() or None
    if isinstance(content, str):
        return content
    return None


def _map_subtasks(
    state: dict[str, Any],
    events: list[EventDTO],
    *,
    selected_workflow: str | None,
    default_finished_at: str,
) -> list[SubtaskDTO]:
    subtasks: list[SubtaskDTO] = []
    seen: set[str] = set()
    for key, (workflow, name) in WORKFLOW_STATE_KEYS.items():
        if key not in state:
            continue
        subtask_id = f"{workflow}:{name}"
        seen.add(subtask_id)
        subtasks.append(
            SubtaskDTO(
                subtask_id=subtask_id,
                name=name,
                status="completed",
                workflow=workflow,
                output_summary=_summarize(state[key]),
                finished_at=default_finished_at,
            )
        )

    for event in events:
        if event.source in {"adk", "user"}:
            continue
        subtask_id = f"agent:{event.source}"
        if subtask_id in seen:
            continue
        seen.add(subtask_id)
        subtasks.append(
            SubtaskDTO(
                subtask_id=subtask_id,
                name=event.source,
                status="completed" if event.type == "final_response" else "running",
                agent_name=event.source,
                workflow=selected_workflow,
                output_summary=event.message,
                finished_at=event.timestamp if event.type == "final_response" else None,
            )
        )
    return subtasks


def _map_progressive_agent_responses(value: Any) -> list[AgentVisibleResponse]:
    """Map progressive response state into typed UI/API contract entries."""

    if value is None:
        return []
    raw_items: Any = value
    if isinstance(value, str):
        try:
            raw_items = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(raw_items, dict):
        raw_items = raw_items.get("progressive_agent_responses") or raw_items.get("responses") or []
    if not isinstance(raw_items, list):
        return []

    responses: list[AgentVisibleResponse] = []
    for index, item in enumerate(raw_items, start=1):
        if isinstance(item, AgentVisibleResponse):
            responses.append(item)
            continue
        if not isinstance(item, dict):
            continue
        response_id = _optional_string(item.get("response_id"))
        agent_name = _optional_string(item.get("agent_name"))
        content = _optional_string(item.get("content"))
        if not response_id or not agent_name or content is None:
            continue
        responses.append(
            AgentVisibleResponse(
                response_id=response_id,
                agent_name=agent_name,
                agent_role=_optional_string(item.get("agent_role")) or "specialist",
                content=content,
                depends_on_response_ids=_string_list(item.get("depends_on_response_ids")),
                visibility=_normalize_progressive_visibility(item.get("visibility")),
                status=_normalize_progressive_status(item.get("status")),
                publication_order=_optional_int(item.get("publication_order")) or index,
                created_at=_optional_string(item.get("created_at")) or utc_now_iso(),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return sorted(responses, key=lambda response: response.publication_order)


def _normalize_progressive_visibility(value: Any) -> str:
    visibility = _optional_string(value) or "user_visible"
    return visibility if visibility in {"internal", "user_visible", "hidden"} else "user_visible"


def _normalize_progressive_status(value: Any) -> str:
    status = _optional_string(value) or "published"
    return status if status in {"draft", "published", "superseded", "failed"} else "published"


def _map_artifacts(artifacts: list[Any] | dict[str, Any] | None) -> list[ArtifactDTO]:
    if not artifacts:
        return []
    items = artifacts.items() if isinstance(artifacts, dict) else enumerate(artifacts)
    mapped: list[ArtifactDTO] = []
    for key, artifact in items:
        name = _extract_value(artifact, "name") or str(key)
        artifact_id = str(_extract_value(artifact, "id", "artifact_id") or name)
        mapped.append(
            ArtifactDTO(
                artifact_id=artifact_id,
                name=str(name),
                mime_type=_optional_string(_extract_value(artifact, "mime_type", "content_type")),
                uri=_optional_string(_extract_value(artifact, "uri", "url")),
                size_bytes=_optional_int(_extract_value(artifact, "size_bytes", "size")),
                metadata={"version": _extract_value(artifact, "version")}
                if _extract_value(artifact, "version") is not None
                else {},
            )
        )
    return mapped


def _summarize(value: Any, max_length: int = 500) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = repr(value)
    return text if len(text) <= max_length else f"{text[: max_length - 1]}…"


def _optional_string(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]
