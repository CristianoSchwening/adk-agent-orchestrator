from __future__ import annotations

import json
from pathlib import Path

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
    with pytest.raises(WorkspaceValidationError, match="complete"):
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

    with pytest.raises(WorkspaceValidationError, match="valid JSON"):
        monitor.observe(agent_name="planner", model_output="plain output")

    violation = tmp_path / "traces" / "session-1" / "planner" / "000002-violation.json"
    assert violation.exists()
    assert (tmp_path / "traces" / "session-1" / "planner" / "000003-failed.json").exists()


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

    agent = create_root_agent(OrchestratorSettings(workspace_enabled=False))
    router = next(node for node in agent.graph.nodes if node.name == "workflow_router_agent")

    assert router.output_schema is None
    assert "WORKSPACE OPERACIONAL VERBALIZADO" not in router.instruction
