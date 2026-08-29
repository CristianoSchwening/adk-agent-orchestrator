from __future__ import annotations

import json
from dataclasses import replace

import pytest

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
