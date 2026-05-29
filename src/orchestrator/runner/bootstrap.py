"""Bootstrap the Google ADK Runner for the phase-1 orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from orchestrator.adk_compat import load_symbol
from orchestrator.agents import create_root_agent
from orchestrator.config import OrchestratorSettings


@dataclass(frozen=True)
class AdkRuntime:
    """Container for ADK runtime objects created in phase 1."""

    settings: OrchestratorSettings
    root_agent: Any
    runner: Any
    session_service: Any
    artifact_service: Any


def build_runtime(settings: OrchestratorSettings | None = None) -> AdkRuntime:
    """Build a Runner with in-memory Session and Artifact services.

    This implements the phase-1 foundation without custom orchestration logic:
    one ADK root agent, one ADK Runner, one in-memory SessionService, and one
    in-memory ArtifactService.
    """

    resolved_settings = settings or OrchestratorSettings.from_env()
    Runner = load_symbol("google.adk.runners", "Runner")
    InMemorySessionService = load_symbol("google.adk.sessions", "InMemorySessionService")
    InMemoryArtifactService = load_symbol("google.adk.artifacts", "InMemoryArtifactService")

    root_agent = create_root_agent(resolved_settings)
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    runner = Runner(
        agent=root_agent,
        app_name=resolved_settings.app_name,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    return AdkRuntime(
        settings=resolved_settings,
        root_agent=root_agent,
        runner=runner,
        session_service=session_service,
        artifact_service=artifact_service,
    )


async def run_once(
    objective: str,
    *,
    settings: OrchestratorSettings | None = None,
    session_id: str | None = None,
) -> str:
    """Execute one user objective through the ADK Runner and return final text."""

    runtime = build_runtime(settings)
    resolved_session_id = session_id or f"session-{uuid4()}"
    await runtime.session_service.create_session(
        app_name=runtime.settings.app_name,
        user_id=runtime.settings.user_id,
        session_id=resolved_session_id,
        state={"phase": "phase_1_foundation"},
    )

    Content = load_symbol("google.genai.types", "Content")
    Part = load_symbol("google.genai.types", "Part")
    user_message = Content(parts=[Part(text=objective)], role="user")

    final_response_text = ""
    async for event in runtime.runner.run_async(
        user_id=runtime.settings.user_id,
        session_id=resolved_session_id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response_text = event.content.parts[0].text or ""
    return final_response_text
