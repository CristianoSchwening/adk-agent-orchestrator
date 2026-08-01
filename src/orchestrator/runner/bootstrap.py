"""Bootstrap the Google ADK Runner for the orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from orchestrator.adk_compat import (
    ensure_certified_adk,
    load_content_classes,
    load_runtime_classes,
)
from orchestrator.agents import create_root_agent
from orchestrator.config import OrchestratorSettings
from orchestrator.contracts import ExecutionContractDTO
from orchestrator.mapping.adk import map_adk_execution, map_duration_ms
from orchestrator.workspace import (
    FileWorkspaceRepository,
    WorkspaceMonitor,
    extract_operational_result,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdkRuntime:
    """Container for ADK runtime objects."""

    settings: OrchestratorSettings
    app: Any
    root_agent: Any
    runner: Any
    session_service: Any
    artifact_service: Any


def build_runtime(settings: OrchestratorSettings | None = None) -> AdkRuntime:
    """Build a Runner with in-memory Session and Artifact services.

    This uses the official ADK Runner with one ADK root agent, in-memory
    SessionService and in-memory ArtifactService.
    """

    resolved_settings = settings or OrchestratorSettings.from_env()
    adk_version = ensure_certified_adk()
    logger.info("Starting orchestrator with certified google-adk version %s", adk_version)
    App, Runner, InMemorySessionService, InMemoryArtifactService = load_runtime_classes()

    root_agent = create_root_agent(resolved_settings)
    app = App(name=resolved_settings.app_name, root_agent=root_agent)
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    runner = Runner(
        app=app,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    return AdkRuntime(
        settings=resolved_settings,
        app=app,
        root_agent=root_agent,
        runner=runner,
        session_service=session_service,
        artifact_service=artifact_service,
    )


def initial_session_state(settings: OrchestratorSettings) -> dict[str, object]:
    """Return the initial ADK session state tracked by the public contract."""

    return {
        "phase": "phase_5_evaluation_production",
        "contract_version": "orchestrator.execution.v1",
        "tool_timeout_seconds": settings.tool_timeout_seconds,
        "mcp_server_count": len(settings.mcp_servers),
        "evaluation_dataset": "eval/datasets/phase5_smoke.json",
        "progressive_agent_responses": [],
        "workspace_enabled": settings.workspace_enabled,
        "workspace_schema_version": "orchestrator.verbalized_workspace.v1",
        "workspace_enforcement": settings.workspace_mode,
        "workspace_trace_root": settings.workspace_root,
        "workspace_trace_count": 0,
    }


async def _create_session(runtime: AdkRuntime, session_id: str) -> Any:
    """Create an ADK session and return the created object when available."""

    return await runtime.session_service.create_session(
        app_name=runtime.settings.app_name,
        user_id=runtime.settings.user_id,
        session_id=session_id,
        state=initial_session_state(runtime.settings),
    )


async def run_once(
    objective: str,
    *,
    settings: OrchestratorSettings | None = None,
    session_id: str | None = None,
) -> str:
    """Execute one user objective through the ADK Runner and return final text."""

    contract = await run_once_contract(objective, settings=settings, session_id=session_id)
    return contract.task.final_response or ""


async def run_once_contract(
    objective: str,
    *,
    settings: OrchestratorSettings | None = None,
    session_id: str | None = None,
) -> ExecutionContractDTO:
    """Execute one objective and return the versioned UI/API execution contract."""

    started = perf_counter()
    runtime = build_runtime(settings)
    resolved_session_id = session_id or f"session-{uuid4()}"
    session = await _create_session(runtime, resolved_session_id)

    Content, Part = load_content_classes()
    user_message = Content(parts=[Part(text=objective)], role="user")

    events: list[Any] = []
    final_response_text = ""
    monitor = _build_workspace_monitor(
        runtime,
        session_id=resolved_session_id,
        objective=objective,
    )
    async for event in runtime.runner.run_async(
        user_id=runtime.settings.user_id,
        session_id=resolved_session_id,
        new_message=user_message,
    ):
        events.append(event)
        if monitor is not None:
            event_type = _runtime_event_type(event)
            is_partial = bool(getattr(event, "partial", False))
            if not is_partial and event_type in {
                "model",
                "final_response",
                "tool_call",
                "tool_response",
            }:
                monitor.observe(
                    agent_name=str(getattr(event, "author", None) or "root_orchestrator_agent"),
                    model_output=_runtime_event_text(event),
                    invocation_id=getattr(event, "invocation_id", None),
                    event_type=event_type,
                )
        if event.is_final_response() and event.content and event.content.parts:
            final_response_text = extract_operational_result(
                event.content.parts[0].text or "",
                objective=objective,
            )

    if monitor is not None:
        for agent_name in sorted(monitor.started_agents):
            monitor.complete(agent_name=agent_name)
        refreshed_session = await _get_session(runtime, resolved_session_id)
        session = refreshed_session or session
        if session is not None and hasattr(session, "state"):
            session.state["workspace_trace_count"] = len(monitor.paths)
            session.state["workspace_violation_count"] = len(monitor.violations)
        events.extend(_workspace_contract_events(monitor))

    return map_adk_execution(
        session=session
        or {
            "session_id": resolved_session_id,
            "app_name": runtime.settings.app_name,
            "user_id": runtime.settings.user_id,
            "state": initial_session_state(runtime.settings),
        },
        events=events,
        objective=objective,
        final_response=final_response_text,
        settings=runtime.settings,
        duration_ms=map_duration_ms(started),
    )


def _build_workspace_monitor(
    runtime: AdkRuntime, *, session_id: str, objective: str
) -> WorkspaceMonitor | None:
    if not runtime.settings.workspace_enabled:
        return None
    repository = FileWorkspaceRepository(
        runtime.settings.workspace_root,
        repository_root=REPOSITORY_ROOT,
        max_bytes=runtime.settings.workspace_max_bytes,
    )
    return WorkspaceMonitor(
        session_id=session_id,
        objective=objective,
        repository=repository,
        mode=runtime.settings.workspace_mode,
        agent_instructions=_agent_instruction_registry(runtime.root_agent),
        agent_tools=_agent_tool_registry(runtime.root_agent),
        session_context=initial_session_state(runtime.settings),
    )


def _agent_instruction_registry(root_agent: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    pending = [root_agent]
    while pending:
        agent = pending.pop()
        name = getattr(agent, "name", None)
        instruction = getattr(agent, "instruction", None)
        if name and instruction:
            result[str(name)] = str(instruction)
        pending.extend(list(getattr(agent, "sub_agents", None) or []))
    return result


def _agent_tool_registry(root_agent: Any) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    pending = [root_agent]
    while pending:
        agent = pending.pop()
        name = getattr(agent, "name", None)
        if name:
            result[str(name)] = [
                {
                    "name": str(
                        getattr(tool, "name", None)
                        or getattr(tool, "__name__", None)
                        or type(tool).__name__
                    ),
                    "description": str(
                        getattr(tool, "description", None)
                        or getattr(tool, "__doc__", None)
                        or ""
                    ).strip(),
                }
                for tool in list(getattr(agent, "tools", None) or [])
            ]
        pending.extend(list(getattr(agent, "sub_agents", None) or []))
    return result


async def _get_session(runtime: AdkRuntime, session_id: str) -> Any:
    getter = getattr(runtime.session_service, "get_session", None)
    if getter is None:
        return None
    return await getter(
        app_name=runtime.settings.app_name,
        user_id=runtime.settings.user_id,
        session_id=session_id,
    )


def _runtime_event_type(event: Any) -> str:
    if callable(getattr(event, "is_final_response", None)) and event.is_final_response():
        return "final_response"
    if getattr(event, "tool_call", None):
        return "tool_call"
    if getattr(event, "tool_response", None):
        return "tool_response"
    if getattr(event, "content", None):
        return "model"
    return "adk_event"


def _runtime_event_text(event: Any) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) if content is not None else None
    if parts:
        return "".join(str(getattr(part, "text", None) or "") for part in parts).strip()
    return str(getattr(event, "message", None) or "")


def _workspace_contract_events(monitor: WorkspaceMonitor) -> list[dict[str, Any]]:
    return [
        {
            "event_id": f"workspace-{record['trace_id']}",
            "event_type": (
                "workspace_violation"
                if record["validation_status"] == "invalid"
                else "workspace_snapshot"
            ),
            "message": (
                f"Verbalized workspace {record['phase']} snapshot persisted for "
                f"{record['agent_name']}."
            ),
            "timestamp": record["timestamp"],
            "source": record["agent_name"],
            "metadata": {
                "trace_id": record["trace_id"],
                "sequence": record["sequence"],
                "phase": record["phase"],
                "path": str(record["path"].relative_to(REPOSITORY_ROOT)),
                "validation_status": record["validation_status"],
            },
        }
        for record in monitor.snapshot_records
    ]
