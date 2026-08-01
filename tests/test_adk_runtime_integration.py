from __future__ import annotations

import asyncio

import pytest

from orchestrator.adk_compat import CERTIFIED_ADK_VERSION, get_adk_version, is_adk_installed
from orchestrator.config import MCPServerSettings, OrchestratorSettings

pytestmark = pytest.mark.skipif(not is_adk_installed(), reason="google-adk is not installed")


def test_build_runtime_uses_certified_app_api():
    from orchestrator.runner import build_runtime

    settings = OrchestratorSettings(
        app_name="adk-runtime-certification",
        model="gemini-flash-latest",
        workspace_enabled=False,
    )

    runtime = build_runtime(settings)

    assert get_adk_version() == CERTIFIED_ADK_VERSION
    assert runtime.app.name == settings.app_name
    assert runtime.app.root_agent is runtime.root_agent
    assert runtime.runner.app is runtime.app
    assert runtime.runner.agent is runtime.root_agent
    assert runtime.runner.app_name == settings.app_name


def test_in_memory_session_and_artifact_lifecycle():
    from google.genai.types import Part

    from orchestrator.runner import build_runtime
    from orchestrator.runner.bootstrap import initial_session_state

    settings = OrchestratorSettings(
        app_name="adk-service-certification",
        user_id="certification-user",
        model="gemini-flash-latest",
        workspace_enabled=False,
    )
    runtime = build_runtime(settings)

    async def exercise_services():
        session = await runtime.session_service.create_session(
            app_name=runtime.app.name,
            user_id=settings.user_id,
            session_id="certification-session",
            state=initial_session_state(settings),
        )
        version = await runtime.artifact_service.save_artifact(
            app_name=runtime.app.name,
            user_id=settings.user_id,
            session_id=session.id,
            filename="result.txt",
            artifact=Part(text="certified artifact"),
        )
        artifact = await runtime.artifact_service.load_artifact(
            app_name=runtime.app.name,
            user_id=settings.user_id,
            session_id=session.id,
            filename="result.txt",
        )
        persisted = await runtime.session_service.get_session(
            app_name=runtime.app.name,
            user_id=settings.user_id,
            session_id=session.id,
        )
        return session, version, artifact, persisted

    session, version, artifact, persisted = asyncio.run(exercise_services())

    assert session.state["contract_version"] == "orchestrator.execution.v1"
    assert version == 0
    assert artifact is not None and artifact.text == "certified artifact"
    assert persisted is not None and persisted.id == session.id


def test_runner_persists_deterministic_event_trajectory():
    from google.adk import Runner
    from google.adk.agents import BaseAgent
    from google.adk.apps import App
    from google.adk.artifacts import InMemoryArtifactService
    from google.adk.events import Event
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    class DeterministicAgent(BaseAgent):
        async def _run_async_impl(self, ctx):
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=Content(role="model", parts=[Part(text="deterministic response")]),
            )

    async def exercise_runner():
        agent = DeterministicAgent(name="deterministic_agent")
        app = App(name="runner-certification", root_agent=agent)
        sessions = InMemorySessionService()
        artifacts = InMemoryArtifactService()
        runner = Runner(app=app, session_service=sessions, artifact_service=artifacts)
        session = await sessions.create_session(
            app_name=app.name,
            user_id="certification-user",
            session_id="runner-session",
        )
        events = [
            event
            async for event in runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=Content(role="user", parts=[Part(text="run")]),
            )
        ]
        persisted = await sessions.get_session(
            app_name=app.name,
            user_id=session.user_id,
            session_id=session.id,
        )
        return events, persisted

    events, persisted = asyncio.run(exercise_runner())

    assert len(events) == 1
    assert events[0].is_final_response()
    assert events[0].content.parts[0].text == "deterministic response"
    assert persisted is not None
    assert [event.author for event in persisted.events] == ["user", "deterministic_agent"]


def test_mcp_toolsets_support_all_configured_transports_without_connecting():
    from orchestrator.mcp import create_configured_mcp_toolsets

    settings = OrchestratorSettings(
        mcp_servers=(
            MCPServerSettings(
                name="stdio",
                transport="stdio",
                command="mcp-server",
                args=("--safe",),
                env={"SAFE": "1"},
            ),
            MCPServerSettings(
                name="sse",
                transport="sse",
                url="https://mcp.example.test/sse",
            ),
            MCPServerSettings(
                name="http",
                transport="streamable_http",
                url="https://mcp.example.test/mcp",
            ),
        )
    )

    toolsets = create_configured_mcp_toolsets(settings)

    assert len(toolsets) == 3
    stdio = toolsets[0].connection_params
    assert stdio.server_params.command == "mcp-server"
    assert stdio.server_params.args == ["--safe"]
    assert toolsets[1].connection_params.url == "https://mcp.example.test/sse"
    assert toolsets[2].connection_params.url == "https://mcp.example.test/mcp"


@pytest.mark.parametrize(
    ("decision", "approved"),
    [("approved", True), ("rejected", False), ("needs_changes", False)],
)
def test_hitl_boundary_preserves_explicit_human_decision(decision, approved):
    from orchestrator.tools import request_human_approval

    result = request_human_approval(
        decision=decision,
        rationale="operator decision",
        requested_action="continue workflow",
    )

    assert result["status"] == "recorded"
    assert result["decision"] == decision
    assert result["approved"] is approved
