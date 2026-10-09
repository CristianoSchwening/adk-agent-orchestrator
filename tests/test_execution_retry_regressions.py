"""Regression coverage for routed outputs and ADK retry deduplication."""

import asyncio
import json

import pytest

from orchestrator.agents import create_task_dispatcher_node
from orchestrator.config import OrchestratorSettings
from orchestrator.context import ContextPackage, Workstream
from orchestrator.planning import Deliverable, Goal, PlannedTask, TaskPlan
from orchestrator.policies import BudgetPolicy


@pytest.mark.parametrize("iterations", [1, 2])
def test_review_workflow_routes_to_final_output(monkeypatch, iterations):
    from google.adk import Runner
    from google.adk.apps import App
    from google.adk.sessions import InMemorySessionService
    from google.adk.workflow import FunctionNode
    from google.genai.types import Content, Part

    from orchestrator.agents import workflows

    calls = []

    def author_factory(settings, *, name, output_key):
        def author(ctx, node_input):
            calls.append(node_input)
            result = f"Roteiro revisado {len(calls)}"
            ctx.state[output_key] = result
            return result
        return FunctionNode(func=author, name=name)

    def critic_factory(settings, *, name, output_key):
        def critic(ctx, node_input):
            ctx.state[output_key] = "Reviewed"
            return "Reviewed"
        return FunctionNode(func=critic, name=name)

    monkeypatch.setattr(workflows, "create_executor_agent", author_factory)
    monkeypatch.setattr(workflows, "create_critic_agent", critic_factory)
    workflow = workflows.create_review_critic_workflow(
        OrchestratorSettings(workspace_enabled=False),
        budget_policy=BudgetPolicy(max_iterations=iterations),
    )

    async def execute():
        sessions = InMemorySessionService()
        app = App(name="review_regression", root_agent=workflow)
        runner = Runner(app=app, session_service=sessions)
        session = await sessions.create_session(app_name=app.name, user_id="test")
        events = [event async for event in runner.run_async(
            user_id="test", session_id=session.id,
            new_message=Content(role="user", parts=[Part(text="Create itinerary")]),
        )]
        return events

    events = asyncio.run(execute())
    assert len(calls) == iterations
    assert any(event.output == f"Roteiro revisado {iterations}" and
               event.node_name == "review_critic_finalizer" for event in events)
    routes = [event.actions.route for event in events if event.actions.route]
    assert routes == ["continue"] * (iterations - 1) + ["done"]


def test_replanned_task_and_guard_do_not_reuse_cached_results(tmp_path):
    task_plan = TaskPlan(
        plan_id="PLAN-RETRY", status="validated", goal=Goal(objective="Create result"),
        tasks=[PlannedTask(task_id="TASK-001", title="Create", description="Create result",
                           task_type="creation", acceptance_criteria=["Result exists"])],
        deliverables=[Deliverable("DEL-001", "Result")],
    )
    node = create_task_dispatcher_node(
        OrchestratorSettings(workspace_enabled=False, task_run_root="runs",
                             task_plan_root="plans", max_replans=1),
        repository_root=tmp_path,
    )
    cache = {}
    executions = []
    evaluations = []

    class Context:
        def __init__(self):
            self.state = {
                "task_plan": task_plan.to_dict(),
                "context_package": ContextPackage(
                    context_id="CTX-RETRY", objective=task_plan.goal.objective,
                    workstream=Workstream("WS-RETRY", "Retry", "Tests"),
                ).to_dict(),
            }

        async def run_node(self, target, *, node_input, run_id):
            # Match ADK same-turn deduplication: completed IDs return old outputs.
            key = (target.name, run_id)
            if key in cache:
                return cache[key]
            payload = json.loads(node_input)
            if target.name == "controlled_replanner_agent":
                previous = payload["previous_plan"]
                result = {key: previous[key] for key in
                          ("goal", "tasks", "deliverables", "assumptions")}
                result["tasks"][0]["acceptance_criteria"].append("Source included")
            elif target.name == "replan_guard_agent":
                evaluations.append(payload)
                passed = len(executions) == 2
                result = {
                    "trigger": "none" if passed else "acceptance_criteria_failed",
                    "rationale": "Checked evidence",
                    "criteria": [{"criterion_id": item["criterion_id"],
                                  "status": "passed" if passed else "failed",
                                  "rationale": "Checked", "evidence": payload["result"]}
                                 for item in payload["acceptance_criteria"]],
                }
            else:
                executions.append(payload)
                result = f"Report attempt {len(executions)}"
            cache[key] = result
            return result

    ctx = Context()
    result = asyncio.run(node._func(ctx=ctx, node_input=""))
    assert result["status"] == "completed"
    assert len(executions) == len(evaluations) == 2
    assert len(evaluations[1]["acceptance_criteria"]) == 2
    assert evaluations[1]["result"] == "Report attempt 2"
    assert result["results"]["TASK-001"] == "Report attempt 2"
