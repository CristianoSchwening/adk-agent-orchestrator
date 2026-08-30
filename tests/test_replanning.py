from __future__ import annotations

import pytest

from orchestrator.planning import Deliverable, Goal, PlannedTask, TaskPlan
from orchestrator.replanning import ReplanRequest, revise_task_plan


def plan() -> TaskPlan:
    return TaskPlan(
        plan_id="PLAN-ORIGINAL",
        lineage_id="PLAN-ORIGINAL",
        status="validated",
        revision=1,
        workstream_id="WS-001",
        goal=Goal(objective="Create a report"),
        tasks=[
            PlannedTask(
                task_id="TASK-001",
                title="Create report",
                description="Produce the report",
                task_type="creation",
                acceptance_criteria=["Report exists"],
            )
        ],
        deliverables=[Deliverable("DEL-001", "Report")],
    )


def revised_draft() -> dict[str, object]:
    return {
        "goal": {
            "objective": "Create a report",
            "constraints": [],
            "success_criteria": ["Report exists"],
        },
        "tasks": [
            {
                "task_id": "TASK-001",
                "title": "Create corrected report",
                "description": "Produce the report after resolving the blocker",
                "task_type": "creation",
                "depends_on": [],
                "required_capabilities": ["creation"],
                "acceptance_criteria": ["Report exists"],
                "strategy": "single_agent",
                "requires_review": False,
                "requires_approval": False,
            }
        ],
        "deliverables": [{"deliverable_id": "DEL-001", "description": "Report"}],
        "assumptions": [],
    }


@pytest.mark.parametrize(
    "trigger",
    [
        "task_failed",
        "blocker_detected",
        "assumption_invalidated",
        "objective_changed",
        "acceptance_criteria_failed",
    ],
)
def test_only_documented_replan_triggers_are_accepted(trigger: str) -> None:
    request = ReplanRequest(trigger=trigger, rationale="Material change")  # type: ignore[arg-type]
    assert request.trigger == trigger


def test_arbitrary_replanning_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported replan trigger"):
        ReplanRequest(trigger="make_it_better", rationale="Preference")  # type: ignore[arg-type]


def test_revision_gets_new_identity_and_preserves_lineage() -> None:
    previous = plan()
    request = ReplanRequest(
        trigger="blocker_detected",
        rationale="A required input is unavailable",
        task_id="TASK-001",
    )

    revised = revise_task_plan(revised_draft(), previous, request)

    assert revised.plan_id != previous.plan_id
    assert revised.revision == 2
    assert revised.lineage_id == "PLAN-ORIGINAL"
    assert revised.parent_plan_id == "PLAN-ORIGINAL"
    assert revised.replan_trigger == "blocker_detected"
    assert revised.workstream_id == "WS-001"


def test_next_revision_keeps_original_lineage() -> None:
    first = revise_task_plan(
        revised_draft(),
        plan(),
        ReplanRequest(trigger="task_failed", rationale="First failure"),
    )
    second = revise_task_plan(
        revised_draft(),
        first,
        ReplanRequest(trigger="assumption_invalidated", rationale="Assumption changed"),
    )

    assert second.revision == 3
    assert second.lineage_id == "PLAN-ORIGINAL"
    assert second.parent_plan_id == first.plan_id
