"""ADK-native strategy dispatcher for validated task plans."""

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
from orchestrator.agents.workflows import create_phase2_workflows
from orchestrator.config import OrchestratorSettings
from orchestrator.context import ContextPackage, build_task_context
from orchestrator.dispatching import FileTaskRunRepository, TaskDispatcher
from orchestrator.planning import TaskPlan


def create_task_dispatcher_node(
    settings: OrchestratorSettings,
    *,
    repository_root: str | Path | None = None,
) -> Any:
    """Create a resumable node that schedules ADK agents or existing workflows."""

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
    # These are the original public/didactic workflows. The strategy dispatcher
    # composes them; it does not replace or hide their standalone factories.
    strategy_workflows = create_phase2_workflows(settings)

    async def dispatch(ctx: Any, node_input: Any) -> dict[str, Any]:
        raw_plan = ctx.state.get("task_plan")
        if not isinstance(raw_plan, dict):
            raise ValueError("dispatcher requires a validated task_plan in session state")
        plan = TaskPlan.from_dict(raw_plan)
        raw_context = ctx.state.get("context_package")
        if not isinstance(raw_context, dict):
            raise ValueError("dispatcher requires a ContextPackage in session state")
        context_package = ContextPackage.from_dict(raw_context)
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
            selection = dispatcher.select_execution(task)
            dispatcher.transition(
                plan,
                run,
                task.task_id,
                "assigned",
                assigned_agent=selection.assigned_agent,
                execution_strategy=selection.strategy,
                execution_node=selection.node_key,
                selection_reason=selection.reason,
            )
            repo.save(run)
            dispatcher.transition(plan, run, task.task_id, "running")
            repo.save(run)
            target = (
                agents[selection.node_key]
                if selection.node_kind == "agent"
                else strategy_workflows[selection.node_key]
            )
            dependency_results = {
                item.task_id: item.result
                for item in run.tasks
                if item.task_id in task.depends_on and item.status == "completed"
            }
            task_context = build_task_context(
                context_package,
                task,
                dependency_results=dependency_results,
                allowed_tool_names=_tool_names(target),
            )
            task_contexts = dict(ctx.state.get("task_contexts") or {})
            task_contexts[task.task_id] = task_context.to_dict()
            ctx.state["task_contexts"] = task_contexts
            task_input = json.dumps(
                {
                    "selected_workflow": ctx.state.get("selected_workflow"),
                    "task_execution_strategy": selection.strategy,
                    "task": task.__dict__,
                    "context": task_context.to_dict(),
                    "instruction": (
                        "Execute somente esta tarefa e satisfaça seus critérios de aceite."
                    ),
                },
                ensure_ascii=False,
            )
            try:
                result = await ctx.run_node(
                    target,
                    node_input=task_input,
                    name=f"{selection.node_key}_{task.task_id.lower()}",
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
        # Stable public name retained for compatibility with Increment 3.
        name="sequential_task_dispatcher",
        rerun_on_resume=True,
    )


def _tool_names(node: Any) -> set[str]:
    """Collect the real tools exposed by an agent or nested workflow."""

    names: set[str] = set()
    pending = [node]
    while pending:
        current = pending.pop()
        for tool in list(getattr(current, "tools", None) or []):
            name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
            if name:
                names.add(str(name))
        graph = getattr(current, "graph", None)
        pending.extend(
            child
            for child in (getattr(graph, "nodes", None) or [])
            if getattr(child, "name", None) != "__START__"
        )
    return names
