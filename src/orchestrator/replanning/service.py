"""Create immutable TaskPlan revisions while retaining their lineage."""

from __future__ import annotations

from dataclasses import replace

from orchestrator.planning import TaskPlan, validate_task_plan
from orchestrator.planning.models import utc_now_iso
from orchestrator.replanning.models import ReplanRequest


def revise_task_plan(draft: object, previous: TaskPlan, request: ReplanRequest) -> TaskPlan:
    from orchestrator.agents.task_planner import task_plan_from_draft

    candidate = task_plan_from_draft(draft, workstream_id=previous.workstream_id)
    revised = replace(
        candidate,
        revision=previous.revision + 1,
        lineage_id=previous.lineage_id or previous.plan_id,
        parent_plan_id=previous.plan_id,
        replan_trigger=request.trigger,
        created_at=previous.created_at,
        updated_at=utc_now_iso(),
    )
    return validate_task_plan(revised)
