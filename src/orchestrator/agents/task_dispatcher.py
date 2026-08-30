"""ADK-native sequential dispatcher for validated task plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orchestrator.adk_compat import load_workflow_classes
from orchestrator.agents.specialists import (
    create_critic_agent,
    create_executor_agent,
    create_planner_agent,
    create_researcher_agent,
    create_summarizer_agent,
)
from orchestrator.config import OrchestratorSettings
from orchestrator.dispatching import FileTaskRunRepository, TaskDispatcher
from orchestrator.planning import TaskPlan


def create_task_dispatcher_node(
    settings: OrchestratorSettings,
    *,
    repository_root: str | Path | None = None,
) -> Any:
    """Create a resumable FunctionNode that schedules selected ADK agents dynamically."""

    _, FunctionNode, _, _, _ = load_workflow_classes()
    dispatcher = TaskDispatcher()
    repo = FileTaskRunRepository(
        settings.task_run_root,
        repository_root=repository_root or Path.cwd(),
        max_bytes=settings.task_run_max_bytes,
    )
    agents = {
        "planner_agent": create_planner_agent(
            settings, name="dispatched_planner_agent", output_key="dispatched_task_result"
        ),
        "researcher_agent": create_researcher_agent(
            settings, name="dispatched_researcher_agent", output_key="dispatched_task_result"
        ),
        "executor_agent": create_executor_agent(
            settings, name="dispatched_executor_agent", output_key="dispatched_task_result"
        ),
        "critic_agent": create_critic_agent(
            settings, name="dispatched_critic_agent", output_key="dispatched_task_result"
        ),
        "summarizer_agent": create_summarizer_agent(
            settings, name="dispatched_summarizer_agent", output_key="dispatched_task_result"
        ),
    }

    async def dispatch(ctx: Any, node_input: Any) -> dict[str, Any]:
        raw_plan = ctx.state.get("task_plan")
        if not isinstance(raw_plan, dict):
            raise ValueError("dispatcher requires a validated task_plan in session state")
        plan = TaskPlan.from_dict(raw_plan)
        run_id = ctx.state.get("task_run_id")
        run = repo.get(str(run_id)) if run_id else None
        if run is None:
            run = dispatcher.initialize(plan)
            repo.save(run)
            ctx.state["task_run_id"] = run.run_id

        while run.status == "running":
            task = dispatcher.next_ready(plan, run)
            if task is None:
                raise RuntimeError("task run is active but has no ready task")
            agent_name, reason = dispatcher.select_agent(task)
            dispatcher.transition(
                plan,
                run,
                task.task_id,
                "assigned",
                assigned_agent=agent_name,
                selection_reason=reason,
            )
            repo.save(run)
            dispatcher.transition(plan, run, task.task_id, "running")
            repo.save(run)
            task_input = json.dumps(
                {
                    "goal": plan.goal.objective,
                    "selected_workflow": ctx.state.get("selected_workflow"),
                    "task": task.__dict__,
                    "completed_dependencies": {
                        item.task_id: item.result
                        for item in run.tasks
                        if item.task_id in task.depends_on and item.status == "completed"
                    },
                    "instruction": (
                        "Execute somente esta tarefa e satisfaça seus critérios de aceite."
                    ),
                },
                ensure_ascii=False,
            )
            try:
                result = await ctx.run_node(
                    agents[agent_name],
                    node_input=task_input,
                    name=f"{agent_name}_{task.task_id.lower()}",
                )
            except Exception as exc:
                dispatcher.transition(plan, run, task.task_id, "failed", error=str(exc))
                repo.save(run)
                ctx.state["task_run"] = run.to_dict()
                raise
            dispatcher.transition(plan, run, task.task_id, "completed", result=result)
            repo.save(run)

        ctx.state["task_run"] = run.to_dict()
        ctx.state["task_run_status"] = run.status
        ctx.state["task_run_path"] = str(repo.save(run).relative_to(repo.repository_root))
        return {
            "plan_id": plan.plan_id,
            "run_id": run.run_id,
            "status": run.status,
            "results": {item.task_id: item.result for item in run.tasks},
        }

    return FunctionNode(
        func=dispatch,
        name="sequential_task_dispatcher",
        rerun_on_resume=True,
    )
