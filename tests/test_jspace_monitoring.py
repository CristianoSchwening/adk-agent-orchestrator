from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.config import OrchestratorSettings
from orchestrator.jspace import (
    FileJSpaceRepository,
    JSpaceMonitor,
    JSpaceValidationError,
    extract_deliberation,
    strip_jspace_metadata,
)
from orchestrator.jspace.models import (
    AgentIdentity,
    JSpaceSnapshot,
    Lifecycle,
    PromptCapture,
    StructuredDeliberation,
)
from orchestrator.runner import initial_session_state

VALID_BLOCK = """
result
<jspace_metadata>
{
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
  "next_action": "complete"
}
</jspace_metadata>
"""


def test_extracts_structured_deliberation():
    state = extract_deliberation(VALID_BLOCK, objective="fallback")

    assert state.objective == "test objective"
    assert state.current_step == "persist snapshot"


def test_strict_monitor_rejects_missing_metadata(tmp_path):
    repository = FileJSpaceRepository(tmp_path / "traces", repository_root=tmp_path)
    monitor = JSpaceMonitor(
        session_id="session-1",
        objective="objective",
        repository=repository,
        mode="strict",
    )

    with pytest.raises(JSpaceValidationError, match="missing"):
        monitor.observe(agent_name="planner", model_output="plain output")

    violation = tmp_path / "traces" / "session-1" / "planner" / "000002-violation.json"
    assert violation.exists()
    assert (tmp_path / "traces" / "session-1" / "planner" / "000003-failed.json").exists()


def test_audit_monitor_persists_full_prompt_and_lifecycle(tmp_path):
    repository = FileJSpaceRepository(tmp_path / "traces", repository_root=tmp_path)
    monitor = JSpaceMonitor(
        session_id="session-1",
        objective="complete user prompt",
        repository=repository,
        mode="audit",
        agent_instructions={"planner": "complete agent instruction"},
        agent_tools={"planner": [{"name": "read_text_file", "description": "Read a file."}]},
    )

    monitor.observe(agent_name="planner", model_output=VALID_BLOCK)
    monitor.complete(agent_name="planner")

    progress_path = tmp_path / "traces" / "session-1" / "planner" / "000002-progress.json"
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    assert payload["prompt_capture"]["input_messages"][0]["content"] == "complete user prompt"
    assert payload["prompt_capture"]["agent_instruction"] == "complete agent instruction"
    assert payload["prompt_capture"]["tool_definitions"][0]["name"] == "read_text_file"
    assert payload["prompt_capture"]["model_output"] == VALID_BLOCK
    assert payload["integrity"]["reasoning_capture"]["is_hidden_chain_of_thought"] is False
    assert (tmp_path / "traces" / "session-1" / "planner" / "000003-completed.json").exists()


def test_repository_rejects_trace_root_outside_repository(tmp_path):
    with pytest.raises(JSpaceValidationError, match="inside"):
        FileJSpaceRepository(tmp_path.parent / "outside", repository_root=tmp_path)


def test_repository_sanitizes_agent_path_and_writes_manifest(tmp_path):
    repository = FileJSpaceRepository("traces", repository_root=tmp_path)
    snapshot = JSpaceSnapshot(
        session_id="session/one",
        sequence=1,
        agent=AgentIdentity(name="../planner"),
        lifecycle=Lifecycle(phase="started", status="running"),
        jspace=StructuredDeliberation(objective="test"),
        prompt_capture=PromptCapture(),
    )

    path = repository.save(snapshot)

    assert path.resolve().is_relative_to(tmp_path.resolve())
    assert ".." not in path.name
    manifest = json.loads((path.parent.parent / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["snapshot_count"] == 1


def test_repository_enforces_snapshot_size(tmp_path):
    repository = FileJSpaceRepository("traces", repository_root=tmp_path, max_bytes=100)
    snapshot = JSpaceSnapshot(
        session_id="session",
        sequence=1,
        agent=AgentIdentity(name="planner"),
        lifecycle=Lifecycle(phase="started", status="running"),
        jspace=StructuredDeliberation(objective="x" * 200),
        prompt_capture=PromptCapture(),
    )

    with pytest.raises(JSpaceValidationError, match="exceeds"):
        repository.save(snapshot)


def test_settings_and_initial_state_enable_strict_jspace(monkeypatch):
    monkeypatch.setenv("ADK_JSPACE_MODE", "audit")
    monkeypatch.setenv("ADK_JSPACE_MAX_BYTES", "8192")

    settings = OrchestratorSettings.from_env()
    state = initial_session_state(settings)

    assert settings.jspace_mode == "audit"
    assert settings.jspace_max_bytes == 8192
    assert state["jspace_schema_version"] == "orchestrator.jspace.v1"
    assert state["jspace_enforcement"] == "audit"


def test_example_snapshot_is_valid_json():
    path = Path("observability/jspace/examples/jspace-state-v1.example.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "orchestrator.jspace.v1"
    assert payload["integrity"]["reasoning_capture"]["is_hidden_chain_of_thought"] is False


def test_monitoring_envelope_is_removed_from_user_visible_text():
    assert strip_jspace_metadata(VALID_BLOCK) == "result"
