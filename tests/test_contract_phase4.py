from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from orchestrator.config import OrchestratorSettings
from orchestrator.contracts import CONTRACT_VERSION, ExecutionContractDTO
from orchestrator.mapping import map_adk_execution
from orchestrator.runner import initial_session_state
from orchestrator.tools import get_orchestrator_status


@dataclass(frozen=True)
class FakeEvent:
    event_id: str
    event_type: str
    message: str
    author: str
    timestamp: str


@dataclass(frozen=True)
class FakeArtifact:
    artifact_id: str
    name: str
    mime_type: str
    uri: str
    size_bytes: int
    version: str


def test_initial_session_state_tracks_phase4_contract_version():
    state = initial_session_state(OrchestratorSettings(tool_timeout_seconds=2.0))

    assert state["phase"] == "phase_5_evaluation_production"
    assert state["contract_version"] == CONTRACT_VERSION
    assert state["tool_timeout_seconds"] == 2.0


def test_status_reports_contract_capabilities():
    status = get_orchestrator_status()

    assert status["phase"] == "phase_5_evaluation_production"
    assert "execution_contract_v1" in status["capabilities"]
    assert "adk_contract_mapper" in status["capabilities"]
    assert "contract_snapshots" in status["capabilities"]


def test_map_adk_execution_returns_versioned_contract():
    contract = map_adk_execution(
        session={
            "session_id": "session-1",
            "app_name": "app",
            "user_id": "user",
            "state": {
                "phase": "phase_5_evaluation_production",
                "workflow": "sequential",
                "sequential_plan": "Plano",
                "decision_rationale": "Objetivo linear.",
                "decision_confidence": "0.9",
                "workflow_alternatives": ["parallel"],
                "policy_version": "phase4-default",
            },
        },
        events=[
            FakeEvent(
                event_id="evt-1",
                event_type="model",
                message="Planner respondeu.",
                author="sequential_planner_agent",
                timestamp="2026-05-30T00:00:00+00:00",
            )
        ],
        artifacts=[
            FakeArtifact(
                artifact_id="artifact-1",
                name="summary.md",
                mime_type="text/markdown",
                uri="artifact://summary.md",
                size_bytes=42,
                version="1",
            )
        ],
        objective="Criar contrato",
        final_response="Contrato criado.",
        settings=OrchestratorSettings(app_name="app", user_id="user"),
        task_id="task-1",
        started_at="2026-05-30T00:00:00+00:00",
        finished_at="2026-05-30T00:00:01+00:00",
        duration_ms=1000,
    )

    assert isinstance(contract, ExecutionContractDTO)
    assert contract.contract_version == CONTRACT_VERSION
    assert contract.task.status == "completed"
    assert contract.task.session_id == "session-1"
    assert contract.subtasks[0].subtask_id == "sequential:plan"
    assert contract.events[0].source == "sequential_planner_agent"
    assert contract.metrics.artifact_count == 1
    assert contract.decision_metadata.selected_workflow == "sequential"
    assert contract.decision_metadata.confidence == 0.9
    assert contract.artifacts[0].metadata == {"version": "1"}


def test_contract_snapshot_shape_is_stable():
    snapshot_path = Path("docs/contracts/execution_contract_v1.example.json")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert snapshot["contract_version"] == CONTRACT_VERSION
    assert set(snapshot) == {
        "contract_version",
        "task",
        "subtasks",
        "events",
        "metrics",
        "decision_metadata",
        "artifacts",
    }
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["decision_metadata"]["selected_workflow"] == "sequential"
    assert snapshot["metrics"]["event_count"] == len(snapshot["events"])
    assert snapshot["metrics"]["subtask_count"] == len(snapshot["subtasks"])
    assert snapshot["metrics"]["artifact_count"] == len(snapshot["artifacts"])


def test_map_adk_execution_supports_parallel_plan_research_execute_summary_keys():
    contract = map_adk_execution(
        session={
            "session_id": "session-parallel",
            "state": {
                "phase": "phase_5_evaluation_production",
                "parallel_plan": "Plano paralelo",
                "parallel_research": "Pesquisa paralela",
                "parallel_execution": "Execução paralela",
                "parallel_summary": "Síntese paralela",
            },
        },
        events=[],
        objective="Executar em paralelo",
        final_response="Síntese paralela",
        settings=OrchestratorSettings(),
        task_id="task-parallel",
        finished_at="2026-05-30T00:00:01+00:00",
    )

    assert contract.decision_metadata.selected_workflow == "parallel"
    assert [subtask.subtask_id for subtask in contract.subtasks] == [
        "parallel:plan",
        "parallel:research",
        "parallel:execute",
        "parallel:summarize",
    ]
