"""Deterministic dependency release and generalist agent selection."""

from __future__ import annotations

from uuid import uuid4

from orchestrator.dispatching.models import PlanRun, TaskRun
from orchestrator.planning import PlannedTask, TaskPlan, validate_task_plan
from orchestrator.planning.models import utc_now_iso

AGENT_CAPABILITIES: dict[str, frozenset[str]] = {
    "planner_agent": frozenset({"planning", "decomposition", "requirements"}),
    "researcher_agent": frozenset({"research", "evidence", "analysis", "source_analysis"}),
    "critic_agent": frozenset({"review", "critique", "validation", "verification", "quality"}),
    "summarizer_agent": frozenset({"synthesis", "summarization", "communication"}),
    "executor_agent": frozenset({"execution", "implementation", "creation", "analysis"}),
}

_TYPE_DEFAULTS = {
    "planning": "planner_agent",
    "research": "researcher_agent",
    "review": "critic_agent",
    "verification": "critic_agent",
    "summary": "summarizer_agent",
    "synthesis": "summarizer_agent",
}


class TaskDispatcher:
    """Advance a validated DAG while allowing only one active task."""

    def initialize(self, plan: TaskPlan) -> PlanRun:
        validate_task_plan(plan)
        roots = {task.task_id for task in plan.tasks if not task.depends_on}
        return PlanRun(
            run_id=f"RUN-{uuid4()}",
            plan_id=plan.plan_id,
            status="running",
            tasks=[
                TaskRun(
                    task_id=task.task_id, status="ready" if task.task_id in roots else "pending"
                )
                for task in plan.tasks
            ],
        )

    def next_ready(self, plan: TaskPlan, run: PlanRun) -> PlannedTask | None:
        states = {task.task_id: task.status for task in run.tasks}
        for task in plan.tasks:
            if states.get(task.task_id) == "ready":
                return task
        return None

    def select_agent(self, task: PlannedTask) -> tuple[str, str]:
        required = {_normalize(value) for value in task.required_capabilities if value.strip()}
        scores = {
            agent: len(required & capabilities)
            for agent, capabilities in AGENT_CAPABILITIES.items()
        }
        best = max(
            scores, key=lambda agent: (scores[agent], -list(AGENT_CAPABILITIES).index(agent))
        )
        if scores[best] > 0:
            return best, f"capability_overlap:{scores[best]}"
        default = _TYPE_DEFAULTS.get(_normalize(task.task_type), "executor_agent")
        return default, f"task_type_fallback:{_normalize(task.task_type) or 'unspecified'}"

    def transition(
        self,
        plan: TaskPlan,
        run: PlanRun,
        task_id: str,
        status: str,
        *,
        assigned_agent: str | None = None,
        selection_reason: str | None = None,
        result: object = None,
        error: str | None = None,
    ) -> PlanRun:
        allowed = {
            "ready": {"assigned"},
            "assigned": {"running"},
            "running": {"completed", "failed"},
        }
        current = next((item for item in run.tasks if item.task_id == task_id), None)
        if current is None or status not in allowed.get(current.status, set()):
            raise ValueError(
                f"invalid task transition {getattr(current, 'status', None)} -> {status}"
            )
        current.status = status  # type: ignore[assignment]
        current.assigned_agent = assigned_agent or current.assigned_agent
        current.selection_reason = selection_reason or current.selection_reason
        current.result = result
        current.error = error
        current.attempt += 1 if status == "running" else 0
        current.updated_at = utc_now_iso()
        if status == "completed":
            self._release_dependents(plan, run)
        elif status == "failed":
            self._block_dependents(plan, run, {task_id})
            run.status = "failed"
        if all(item.status == "completed" for item in run.tasks):
            run.status = "completed"
        run.updated_at = utc_now_iso()
        return run

    @staticmethod
    def _release_dependents(plan: TaskPlan, run: PlanRun) -> None:
        states = {task.task_id: task.status for task in run.tasks}
        by_id = {task.task_id: task for task in run.tasks}
        for task in plan.tasks:
            if states[task.task_id] == "pending" and all(
                states.get(dependency) == "completed" for dependency in task.depends_on
            ):
                by_id[task.task_id].status = "ready"
                by_id[task.task_id].updated_at = utc_now_iso()

    @staticmethod
    def _block_dependents(plan: TaskPlan, run: PlanRun, failed: set[str]) -> None:
        by_id = {task.task_id: task for task in run.tasks}
        changed = True
        while changed:
            changed = False
            for task in plan.tasks:
                state = by_id[task.task_id]
                if state.status in {"pending", "ready"} and any(
                    dependency in failed for dependency in task.depends_on
                ):
                    state.status = "blocked"
                    state.updated_at = utc_now_iso()
                    failed.add(task.task_id)
                    changed = True


def _normalize(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")
