from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from orchestrator.agents.task_planner import task_plan_from_draft
from orchestrator.config import OrchestratorSettings
from orchestrator.mapping import map_adk_execution
from orchestrator.planning import (
    Deliverable,
    FileTaskPlanRepository,
    Goal,
    PlannedTask,
    TaskPlan,
    TaskPlanValidationError,
    validate_task_plan,
)


def sample_plan() -> TaskPlan:
    return TaskPlan(
        plan_id="PLAN-001",
        status="validated",
        goal=Goal(
            objective="Produce a general-purpose implementation proposal",
            constraints=["Remain domain neutral"],
            success_criteria=["The plan is actionable"],
        ),
        tasks=[
            PlannedTask(
                task_id="TASK-001",
                title="Analyze inputs",
                description="Identify requirements and constraints.",
                task_type="analysis",
                acceptance_criteria=["Requirements are explicit"],
            ),
            PlannedTask(
                task_id="TASK-002",
                title="Produce proposal",
                description="Create the requested deliverable.",
                task_type="creation",
                depends_on=["TASK-001"],
                required_capabilities=["synthesis"],
                acceptance_criteria=["Deliverable satisfies the goal"],
                strategy="review_critic",
                requires_review=True,
            ),
        ],
        deliverables=[Deliverable("DEL-001", "Implementation proposal")],
    )


def test_validates_general_purpose_task_plan() -> None:
    plan = sample_plan()

    assert validate_task_plan(plan) is plan
    assert plan.tasks[1].depends_on == ["TASK-001"]
    assert plan.schema_version == "orchestrator.task_plan.v1"


def test_rejects_cycles_and_unknown_dependencies() -> None:
    plan = sample_plan()
    cyclic = replace(
        plan,
        tasks=[
            replace(plan.tasks[0], depends_on=["TASK-002"]),
            replace(plan.tasks[1], depends_on=["TASK-001", "TASK-404"]),
        ],
    )

    with pytest.raises(TaskPlanValidationError) as exc_info:
        validate_task_plan(cyclic)

    assert "unknown dependencies: TASK-404" in str(exc_info.value)


def test_rejects_dependency_cycle() -> None:
    plan = sample_plan()
    cyclic = replace(
        plan,
        tasks=[
            replace(plan.tasks[0], depends_on=["TASK-002"]),
            replace(plan.tasks[1], depends_on=["TASK-001"]),
        ],
    )

    with pytest.raises(TaskPlanValidationError, match="contains a cycle"):
        validate_task_plan(cyclic)


def test_repository_round_trips_with_atomic_json(tmp_path) -> None:
    repository = FileTaskPlanRepository(
        "plans",
        repository_root=tmp_path,
    )

    plan = sample_plan()
    path = repository.save(plan)
    restored = repository.get("PLAN-001")

    assert path == tmp_path / "plans" / "PLAN-001.json"
    assert restored == plan
    assert not path.with_suffix(".json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["plan_id"] == "PLAN-001"


def test_repository_rejects_path_traversal(tmp_path) -> None:
    repository = FileTaskPlanRepository("plans", repository_root=tmp_path)

    with pytest.raises(TaskPlanValidationError, match="unsafe path"):
        repository.get("../outside")


def test_contract_projects_valid_plan_from_session_state() -> None:
    plan = sample_plan()
    contract = map_adk_execution(
        session={"session_id": "session-plan", "state": {"task_plan": plan.to_dict()}},
        events=[],
        objective=plan.goal.objective,
        final_response="",
        settings=OrchestratorSettings(),
    )

    assert contract.task_plan is not None
    assert contract.task_plan["plan_id"] == "PLAN-001"
    assert contract.task_plan["tasks"][1]["depends_on"] == ["TASK-001"]


def test_llm_draft_materializes_as_versioned_validated_plan() -> None:
    draft = {
        "goal": {
            "objective": "Analyze a dataset",
            "constraints": ["Use the supplied data"],
            "success_criteria": ["Findings are supported by evidence"],
        },
        "tasks": [
            {
                "task_id": "TASK-001",
                "title": "Inspect data",
                "description": "Identify the available fields and quality issues.",
                "task_type": "analysis",
                "depends_on": [],
                "required_capabilities": ["data_analysis"],
                "acceptance_criteria": ["Data quality is described"],
                "strategy": "single_agent",
                "requires_review": False,
                "requires_approval": False,
            }
        ],
        "deliverables": [
            {"deliverable_id": "DEL-001", "description": "Evidence-backed findings"}
        ],
        "assumptions": [],
    }

    plan = task_plan_from_draft(draft)

    assert plan.plan_id.startswith("PLAN-")
    assert plan.status == "validated"
    assert plan.tasks[0].required_capabilities == ["data_analysis"]


def test_llm_draft_rejects_cyclic_task_dependencies() -> None:
    draft = {
        "goal": {
            "objective": "Create a document",
            "constraints": [],
            "success_criteria": ["Document is complete"],
        },
        "tasks": [
            {
                "task_id": "TASK-001",
                "title": "Draft",
                "description": "Draft the document.",
                "task_type": "creation",
                "depends_on": ["TASK-002"],
                "required_capabilities": ["writing"],
                "acceptance_criteria": ["Draft exists"],
                "strategy": "single_agent",
                "requires_review": False,
                "requires_approval": False,
            },
            {
                "task_id": "TASK-002",
                "title": "Review",
                "description": "Review the document.",
                "task_type": "review",
                "depends_on": ["TASK-001"],
                "required_capabilities": ["review"],
                "acceptance_criteria": ["Review is complete"],
                "strategy": "review_critic",
                "requires_review": True,
                "requires_approval": False,
            },
        ],
        "deliverables": [{"deliverable_id": "DEL-001", "description": "Document"}],
        "assumptions": [],
    }

    with pytest.raises(TaskPlanValidationError, match="contains a cycle"):
        task_plan_from_draft(draft)


def test_runtime_persists_generated_plan_and_records_relative_path(
    tmp_path, monkeypatch
) -> None:
    from orchestrator.runner import bootstrap

    plan = sample_plan()
    monkeypatch.setattr(bootstrap, "REPOSITORY_ROOT", tmp_path)
    settings = OrchestratorSettings(
        task_plan_root=str(tmp_path / "plans"),
        task_plan_max_bytes=262_144,
    )
    runtime = SimpleNamespace(settings=settings)
    session = {"state": {"task_plan": plan.to_dict()}}

    bootstrap._persist_generated_task_plan(runtime, session)

    assert (tmp_path / "plans" / "PLAN-001.json").exists()
    assert session["state"]["task_plan_path"].endswith("PLAN-001.json")
