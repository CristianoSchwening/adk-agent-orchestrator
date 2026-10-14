"""Regression coverage for routed outputs and ADK retry deduplication."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from orchestrator.agents import create_task_dispatcher_node
from orchestrator.config import OrchestratorSettings
from orchestrator.context import ContextPackage, Workstream
from orchestrator.planning import Deliverable, Goal, PlannedTask, TaskPlan
from orchestrator.policies import BudgetPolicy


@pytest.mark.parametrize("failure", ["before", "after"])
def test_adk_dispatcher_resume_after_process_exit_does_not_repeat_effect(tmp_path, failure):
    worker = Path(__file__).with_name("dispatcher_restart_worker.py")
    first = subprocess.run([sys.executable, str(worker), str(tmp_path), "start", failure],
                           capture_output=True, text=True, timeout=60)
    assert first.returncode == 23, first.stdout + first.stderr
    for _ in range(2):
        resumed = subprocess.run([sys.executable, str(worker), str(tmp_path), "resume", failure],
                                 capture_output=True, text=True, timeout=60)
        assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    effects = tmp_path / "effects.txt"
    assert (effects.read_text(encoding="utf-8").splitlines() if effects.exists() else []) == (
        ["external action"] if failure == "after" else [])
    runs = list((tmp_path / "runs").glob("RUN-*.json"))
    assert len(runs) == 1
    saved = json.loads(runs[0].read_text(encoding="utf-8"))
    assert saved["status"] == "failed"
    assert saved["terminal_error"]["code"] == "execution_outcome_unknown"


@pytest.mark.parametrize("failure", [
    "before", "after", "crash", "legacy", "after_return", "concurrent",
])
def test_dispatcher_never_replays_uncertain_action_after_restart(tmp_path, failure):
    from orchestrator.dispatching import FileTaskRunRepository

    plan = TaskPlan(
        plan_id="PLAN-EFFECT", status="validated", goal=Goal(objective="Apply an action"),
        tasks=[PlannedTask(task_id="TASK-001", title="Apply", description="Apply action",
                           task_type="creation", acceptance_criteria=["Action applied"])],
        deliverables=[Deliverable("DEL-001", "Action")],
    )
    settings = OrchestratorSettings(workspace_enabled=False, task_run_root="runs",
                                    task_plan_root="plans", max_replans=2)
    state = {"task_plan": plan.to_dict(), "context_package": ContextPackage(
        context_id="CTX-EFFECT", objective=plan.goal.objective,
        workstream=Workstream("WS-EFFECT", "Action", "Tests")).to_dict()}
    effects = []
    invocations = []

    class ProcessStopped(BaseException):
        pass

    class Context:
        session = SimpleNamespace(id="persistent-session")
        invocation_id = "persistent-invocation"

        def __init__(self, restarted=False):
            # No task_run_id survives: model a lost ADK state delta.
            self.state = dict(state)
            self.restarted = restarted
            if restarted and failure == "crash":
                self.state["replan_request"] = {
                    "trigger": "task_failed", "rationale": "Retry after restart"}

        async def run_node(self, target, *, node_input, run_id):
            if target.name == "controlled_replanner_agent":
                raise AssertionError("uncertain actions must not be replanned")
            if target.name == "replan_guard_agent":
                if not self.restarted and failure == "after_return":
                    raise ProcessStopped()
                criteria = json.loads(node_input)["acceptance_criteria"]
                return {"trigger": "none", "rationale": "Checked", "criteria": [
                    {"criterion_id": item["criterion_id"], "status": "passed",
                     "rationale": "Checked", "evidence": "Action"} for item in criteria]}
            invocations.append(run_id)
            if failure == "concurrent":
                from orchestrator.runner.human_runs import RunBusyError

                competing = create_task_dispatcher_node(settings, repository_root=tmp_path)
                with pytest.raises(RunBusyError):
                    await competing._func(ctx=Context(restarted=True), node_input="")
            if failure == "before":
                raise ValueError("failed before external effect")
            effects.append("external effect")
            if failure == "after":
                raise ValueError("failed after external effect")
            if failure in {"crash", "legacy"}:
                raise ProcessStopped()
            return "Applied"

    node = create_task_dispatcher_node(settings, repository_root=tmp_path)
    first = Context()
    if failure in {"crash", "legacy", "after_return"}:
        with pytest.raises(ProcessStopped):
            asyncio.run(node._func(ctx=first, node_input=""))
    else:
        assert asyncio.run(node._func(ctx=first, node_input=""))["status"] == (
            "completed" if failure == "concurrent" else "failed")
    if failure == "legacy":
        record = next((tmp_path / "runs").glob("RUN-*.json"))
        legacy = json.loads(record.read_text(encoding="utf-8"))
        legacy["tasks"][0].pop("execution_pending")
        record.write_text(json.dumps(legacy), encoding="utf-8")
    # New node, repository and context; no ADK result cache.
    restarted = Context(restarted=True)
    node = create_task_dispatcher_node(settings, repository_root=tmp_path)
    result = asyncio.run(node._func(ctx=restarted, node_input=""))
    assert result["status"] == (
        "completed" if failure in {"after_return", "concurrent"} else "failed")
    assert len(invocations) == 1
    assert len(effects) == (0 if failure == "before" else 1)
    saved = FileTaskRunRepository("runs", repository_root=tmp_path).get(result["run_id"])
    if failure in {"after_return", "concurrent"}:
        assert saved.tasks[0].result == "Applied"
    else:
        assert saved.terminal_error["code"] == "execution_outcome_unknown"
        assert saved.tasks[0].status == "failed"


@pytest.mark.parametrize("iterations", [1, 2])
@pytest.mark.parametrize("workflow_name", ["review_critic", "iterative_refinement"])
def test_review_workflow_routes_to_final_output(monkeypatch, iterations, workflow_name):
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
    monkeypatch.setattr(workflows, "create_planner_agent", author_factory)
    monkeypatch.setattr(workflows, "create_evaluator_agent", lambda settings: critic_factory(
        settings, name="refinement_evaluator_agent", output_key="refinement_evaluation",
    ))

    def editor_factory(settings, *, name, output_key):
        def editor(ctx, node_input):
            result = f"Roteiro revisado {len(calls)}"
            ctx.state[output_key] = result
            return result
        return FunctionNode(func=editor, name=name)

    monkeypatch.setattr(workflows, "create_refiner_agent", editor_factory)
    factory = getattr(workflows, f"create_{workflow_name}_workflow")
    workflow = factory(
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
    if iterations > 1:
        assert calls[1]["task_input"] == "Create itinerary"
        assert calls[1]["previous_result"] == "Roteiro revisado 1"
        assert calls[1]["review_feedback"] == (
            "Reviewed" if workflow_name == "review_critic" else "Roteiro revisado 1"
        )
    assert any(event.output == f"Roteiro revisado {iterations}" and
               event.node_name == f"{workflow_name}_finalizer" for event in events)
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
