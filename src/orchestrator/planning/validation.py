"""Deterministic validation for task-plan DAGs."""

from __future__ import annotations

from orchestrator.planning.models import TASK_PLAN_SCHEMA_VERSION, TaskPlan

_PLAN_STATUSES = {"draft", "validated", "archived"}
_TASK_STRATEGIES = {
    "single_agent",
    "sequential",
    "parallel",
    "review_critic",
    "iterative_refinement",
    "human_in_the_loop",
    "verification",
}


class TaskPlanValidationError(ValueError):
    """Raised when a task plan is structurally unsafe or incomplete."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_task_plan(plan: TaskPlan, *, max_tasks: int = 50) -> TaskPlan:
    """Validate identifiers, references, acceptance criteria and acyclicity."""

    errors: list[str] = []
    if plan.schema_version != TASK_PLAN_SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {plan.schema_version}")
    if not plan.plan_id.strip():
        errors.append("plan_id is required")
    if not plan.goal.objective.strip():
        errors.append("goal.objective is required")
    if plan.status not in _PLAN_STATUSES:
        errors.append(f"unsupported plan status: {plan.status}")
    if plan.revision < 1:
        errors.append("revision must be greater than zero")
    if not plan.deliverables:
        errors.append("at least one deliverable is required")
    if not plan.tasks:
        errors.append("at least one task is required")
    if len(plan.tasks) > max_tasks:
        errors.append(f"task count exceeds maximum of {max_tasks}")

    task_ids = [task.task_id for task in plan.tasks]
    if any(not task_id.strip() for task_id in task_ids):
        errors.append("every task requires a non-empty task_id")
    duplicates = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
    if duplicates:
        errors.append(f"duplicate task ids: {', '.join(duplicates)}")
    known = set(task_ids)
    for task in plan.tasks:
        if not task.title.strip():
            errors.append(f"task {task.task_id or '<empty>'} requires a title")
        if not task.description.strip():
            errors.append(f"task {task.task_id or '<empty>'} requires a description")
        if not task.task_type.strip():
            errors.append(f"task {task.task_id or '<empty>'} requires a task_type")
        if not task.acceptance_criteria:
            errors.append(f"task {task.task_id or '<empty>'} requires acceptance criteria")
        if task.strategy not in _TASK_STRATEGIES:
            errors.append(f"task {task.task_id} uses unsupported strategy: {task.strategy}")
        unknown = sorted(set(task.depends_on) - known)
        if unknown:
            errors.append(f"task {task.task_id} has unknown dependencies: {', '.join(unknown)}")
        if task.task_id in task.depends_on:
            errors.append(f"task {task.task_id} cannot depend on itself")

    if not errors and _has_cycle(plan):
        errors.append("task dependency graph contains a cycle")
    if plan.tasks and not any(not task.depends_on for task in plan.tasks):
        errors.append("task graph requires at least one root task")
    depended_on = {dependency for task in plan.tasks for dependency in task.depends_on}
    if plan.tasks and not any(task.task_id not in depended_on for task in plan.tasks):
        errors.append("task graph requires at least one terminal task")

    deliverable_ids = [item.deliverable_id for item in plan.deliverables]
    if any(not item.strip() for item in deliverable_ids):
        errors.append("every deliverable requires a non-empty deliverable_id")
    if len(set(deliverable_ids)) != len(deliverable_ids):
        errors.append("deliverable ids must be unique")
    for deliverable in plan.deliverables:
        if not deliverable.description.strip():
            errors.append(f"deliverable {deliverable.deliverable_id} requires a description")

    if errors:
        raise TaskPlanValidationError(errors)
    return plan


def _has_cycle(plan: TaskPlan) -> bool:
    dependencies = {task.task_id: task.depends_on for task in plan.tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in visiting:
            return True
        if task_id in visited:
            return False
        visiting.add(task_id)
        if any(visit(dependency) for dependency in dependencies[task_id]):
            return True
        visiting.remove(task_id)
        visited.add(task_id)
        return False

    return any(visit(task_id) for task_id in dependencies)
