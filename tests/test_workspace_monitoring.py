from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from orchestrator.config import OrchestratorSettings
from orchestrator.runner import initial_session_state
from orchestrator.workspace import (
    AGENT_STEP_RESPONSE_SCHEMA,
    FileWorkspaceRepository,
    WorkspaceMonitor,
    WorkspaceValidationError,
    extract_operational_result,
    extract_workspace,
    parse_agent_step,
)
from orchestrator.workspace.models import (
    AgentIdentity,
    Lifecycle,
    PromptCapture,
    VerbalizedWorkspace,
    WorkspaceSnapshot,
)

VALID_RESPONSE = json.dumps(
    {
        "workspace": {
            "objective": "test objective",
            "interpretation": "validate monitoring",
            "current_step": "persist snapshot",
            "plan": [],
            "assumptions": [],
            "hypotheses": [],
            "evidence": [],
            "decisions": [],
            "uncertainties": [],
            "blockers": [],
            "criticisms": [],
            "next_action": "complete",
        },
        "result": "operational result",
    }
)


def test_extracts_workspace_and_operational_result():
    workspace = extract_workspace(VALID_RESPONSE, objective="fallback")

    assert workspace.objective == "test objective"
    assert workspace.current_step == "persist snapshot"
    assert extract_operational_result(VALID_RESPONSE) == "operational result"


def test_rejects_partial_or_extra_json_before_exposing_result():
    with pytest.raises(WorkspaceValidationError, match="malformed JSON"):
        extract_operational_result('{"workspace":')

    payload = json.loads(VALID_RESPONSE)
    payload["untrusted_extra"] = True
    with pytest.raises(WorkspaceValidationError, match="exactly"):
        extract_operational_result(json.dumps(payload))


def test_strict_monitor_rejects_missing_workspace(tmp_path):
    repository = FileWorkspaceRepository(tmp_path / "traces", repository_root=tmp_path)
    monitor = WorkspaceMonitor(
        session_id="session-1",
        objective="objective",
        repository=repository,
        mode="strict",
    )

    with pytest.raises(WorkspaceValidationError, match="malformed JSON"):
        monitor.observe(agent_name="planner", model_output="plain output")

    violation = tmp_path / "traces" / "session-1" / "planner" / "000002-violation.json"
    assert violation.exists()
    assert (tmp_path / "traces" / "session-1" / "planner" / "000003-failed.json").exists()


def test_strict_monitor_reports_empty_response_with_provider_diagnostic(tmp_path):
    repository = FileWorkspaceRepository(tmp_path / "traces", repository_root=tmp_path)
    monitor = WorkspaceMonitor(
        session_id="session-empty",
        objective="objective",
        repository=repository,
        mode="strict",
    )

    with pytest.raises(
        WorkspaceValidationError,
        match="empty textual response.*finish_reason=SAFETY",
    ):
        monitor.observe(
            agent_name="root",
            model_output="",
            event_type="final_response",
            event_diagnostic="finish_reason=SAFETY",
        )

    violation = tmp_path / "traces" / "session-empty" / "root" / "000002-violation.json"
    payload = json.loads(violation.read_text(encoding="utf-8"))
    assert payload["prompt_capture"]["model_output"] == ""
    assert "finish_reason=SAFETY" in payload["workspace"]["blockers"][0]


def test_audit_monitor_persists_full_prompt_and_lifecycle(tmp_path):
    repository = FileWorkspaceRepository(tmp_path / "traces", repository_root=tmp_path)
    monitor = WorkspaceMonitor(
        session_id="session-1",
        objective="complete user prompt",
        repository=repository,
        mode="audit",
        agent_instructions={"planner": "complete agent instruction"},
        agent_tools={"planner": [{"name": "read_text_file", "description": "Read a file."}]},
    )

    monitor.observe(agent_name="planner", model_output=VALID_RESPONSE)
    monitor.complete(agent_name="planner")

    progress_path = tmp_path / "traces" / "session-1" / "planner" / "000002-progress.json"
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    assert payload["workspace"]["objective"] == "test objective"
    assert payload["prompt_capture"]["input_messages"][0]["content"] == "complete user prompt"
    assert payload["prompt_capture"]["agent_instruction"] == "complete agent instruction"
    assert payload["prompt_capture"]["tool_definitions"][0]["name"] == "read_text_file"
    assert payload["prompt_capture"]["model_output"] == VALID_RESPONSE
    assert payload["integrity"]["reasoning_capture"]["is_hidden_chain_of_thought"] is False
    assert (tmp_path / "traces" / "session-1" / "planner" / "000003-completed.json").exists()


def test_repository_rejects_trace_root_outside_repository(tmp_path):
    with pytest.raises(WorkspaceValidationError, match="inside"):
        FileWorkspaceRepository(tmp_path.parent / "outside", repository_root=tmp_path)


def test_repository_sanitizes_agent_path_and_writes_manifest(tmp_path):
    repository = FileWorkspaceRepository("traces", repository_root=tmp_path)
    snapshot = WorkspaceSnapshot(
        session_id="session/one",
        sequence=1,
        agent=AgentIdentity(name="../planner"),
        lifecycle=Lifecycle(phase="started", status="running"),
        workspace=VerbalizedWorkspace(objective="test"),
        prompt_capture=PromptCapture(),
    )

    path = repository.save(snapshot)

    assert path.resolve().is_relative_to(tmp_path.resolve())
    assert ".." not in path.name
    manifest = json.loads((path.parent.parent / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["snapshot_count"] == 1


def test_repository_enforces_snapshot_size(tmp_path):
    repository = FileWorkspaceRepository("traces", repository_root=tmp_path, max_bytes=100)
    snapshot = WorkspaceSnapshot(
        session_id="session",
        sequence=1,
        agent=AgentIdentity(name="planner"),
        lifecycle=Lifecycle(phase="started", status="running"),
        workspace=VerbalizedWorkspace(objective="x" * 200),
        prompt_capture=PromptCapture(),
    )

    with pytest.raises(WorkspaceValidationError, match="exceeds"):
        repository.save(snapshot)


def test_settings_and_initial_state_enable_strict_workspace(monkeypatch):
    monkeypatch.setenv("ADK_WORKSPACE_MODE", "audit")
    monkeypatch.setenv("ADK_WORKSPACE_MAX_BYTES", "8192")

    settings = OrchestratorSettings.from_env()
    state = initial_session_state(settings)

    assert settings.workspace_mode == "audit"
    assert settings.workspace_max_bytes == 8192
    assert state["workspace_schema_version"] == "orchestrator.verbalized_workspace.v1"
    assert state["workspace_enforcement"] == "audit"


def test_example_snapshot_is_valid_json():
    path = Path("observability/verbalized_workspace/examples/verbalized-workspace-v1.example.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(
        Path(
            "observability/verbalized_workspace/schema/verbalized-workspace-v1.schema.json"
        ).read_text(encoding="utf-8")
    )

    assert payload["schema_version"] == "orchestrator.verbalized_workspace.v1"
    assert payload["integrity"]["reasoning_capture"]["is_hidden_chain_of_thought"] is False
    Draft202012Validator(schema).validate(payload)


def test_adk_output_schema_requires_workspace_before_result_contractually():
    assert AGENT_STEP_RESPONSE_SCHEMA["required"] == ["workspace", "result"]
    assert AGENT_STEP_RESPONSE_SCHEMA["additionalProperties"] is False


def test_workspace_can_be_disabled_for_plain_agent_outputs():
    from orchestrator.agents import create_root_agent
    from orchestrator.runner.bootstrap import _extract_final_response

    agent = create_root_agent(OrchestratorSettings(workspace_enabled=False))
    router = next(node for node in agent.graph.nodes if node.name == "workflow_router_agent")

    assert router.output_schema is None
    assert "WORKSPACE OPERACIONAL VERBALIZADO" not in router.instruction
    assert (
        _extract_final_response(
            "plain Gemini response",
            objective="test objective",
            workspace_enabled=False,
        )
        == "plain Gemini response"
    )


def test_workspace_enabled_requires_structured_final_response():
    from orchestrator.runner.bootstrap import _extract_final_response

    assert (
        _extract_final_response(
            VALID_RESPONSE,
            objective="test objective",
            workspace_enabled=True,
        )
        == "operational result"
    )
    with pytest.raises(WorkspaceValidationError, match="malformed JSON"):
        _extract_final_response(
            "plain Gemini response",
            objective="test objective",
            workspace_enabled=True,
        )


def test_runtime_event_diagnostic_preserves_provider_termination_details():
    from orchestrator.runner.bootstrap import _runtime_event_diagnostic

    event = SimpleNamespace(
        finish_reason="MAX_TOKENS",
        error_code="MODEL_OUTPUT_LIMIT",
        error_message="Response stopped before completion",
        turn_complete=True,
        interrupted=False,
    )

    diagnostic = _runtime_event_diagnostic(event)

    assert diagnostic is not None
    assert "finish_reason=MAX_TOKENS" in diagnostic
    assert "error_code=MODEL_OUTPUT_LIMIT" in diagnostic
    assert "error_message=Response stopped before completion" in diagnostic
    assert "turn_complete=True" in diagnostic


def test_router_bare_route_is_normalized_to_workspace_contract():
    from orchestrator.runner.bootstrap import _normalize_router_output

    normalized = _normalize_router_output(
        '"sequential"',
        agent_name="workflow_router_agent",
        event_type="final_response",
        objective="answer a simple question",
    )
    workspace, result = parse_agent_step(normalized, objective="fallback")

    assert result == "sequential"
    assert workspace.objective == "answer a simple question"
    assert workspace.decisions[0]["selected_workflow"] == "sequential"


def test_router_normalizer_preserves_complete_or_invalid_outputs():
    from orchestrator.runner.bootstrap import _normalize_router_output

    assert _normalize_router_output(
        VALID_RESPONSE,
        agent_name="workflow_router_agent",
        event_type="model",
        objective="objective",
    ) == VALID_RESPONSE
    assert _normalize_router_output(
        '"unknown_workflow"',
        agent_name="workflow_router_agent",
        event_type="model",
        objective="objective",
    ) == '"unknown_workflow"'
    assert _normalize_router_output(
        '"sequential"',
        agent_name="planner_agent",
        event_type="model",
        objective="objective",
    ) == '"sequential"'


def test_progressive_events_are_materialized_into_canonical_responses():
    from orchestrator.runner.bootstrap import _materialize_progressive_agent_responses

    def event(author: str, payload: dict, timestamp: float):
        part = SimpleNamespace(text=f"```json\n{json.dumps(payload)}\n```")
        return SimpleNamespace(
            author=author,
            content=SimpleNamespace(parts=[part]),
            timestamp=timestamp,
        )

    events = [
        event(
            "progressive_agent_b",
            {"content": "Pesquisa independente", "agent_role": "researcher"},
            2.0,
        ),
        event("progressive_agent_a", {"content": "Plano independente"}, 1.0),
        event("progressive_agent_c", {"content": "Síntese conjunta"}, 3.0),
    ]

    responses = _materialize_progressive_agent_responses(events)

    assert [item["response_id"] for item in responses] == [
        "response-x",
        "response-z",
        "response-c",
    ]
    assert responses[0]["depends_on_response_ids"] == []
    assert responses[1]["depends_on_response_ids"] == []
    assert responses[2]["depends_on_response_ids"] == ["response-x", "response-z"]
    assert all(item["metadata"]["materialized_from_event"] for item in responses)


def test_progressive_event_materializer_unwraps_nested_response_content():
    from orchestrator.runner.bootstrap import _materialize_progressive_agent_responses

    nested = {
        "response_id": "response-c",
        "agent_name": "progressive_agent_c",
        "content": "Relatório consolidado",
    }
    outer = {
        "response_id": "response-c",
        "agent_name": "progressive_agent_c",
        "content": json.dumps(nested),
    }
    event = SimpleNamespace(
        author="progressive_agent_c",
        content=SimpleNamespace(parts=[SimpleNamespace(text=json.dumps(outer))]),
        timestamp=3.0,
    )

    responses = _materialize_progressive_agent_responses([event])

    assert responses[0]["content"] == "Relatório consolidado"


def test_workspace_schema_is_preserved_on_graph_router():
    from orchestrator.agents import create_root_agent

    agent = create_root_agent(OrchestratorSettings(workspace_enabled=True))
    router = next(node for node in agent.graph.nodes if node.name == "workflow_router_agent")

    assert router.output_schema == AGENT_STEP_RESPONSE_SCHEMA
    assert "WORKSPACE OPERACIONAL VERBALIZADO" in router.instruction
