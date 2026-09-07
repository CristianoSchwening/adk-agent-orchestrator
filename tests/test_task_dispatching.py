from __future__ import annotations

import asyncio

import pytest

from orchestrator.agents import create_phase2_workflows, create_task_dispatcher_node
from orchestrator.config import OrchestratorSettings
from orchestrator.context import ContextPackage, Workstream
from orchestrator.dispatching import STRATEGY_WORKFLOWS, FileTaskRunRepository, TaskDispatcher
from orchestrator.mapping import map_adk_execution
from orchestrator.planning import Deliverable, Goal, PlannedTask, TaskPlan


def plan() -> TaskPlan:
    return TaskPlan(
        plan_id="PLAN-DISPATCH",
        status="validated",
        goal=Goal(objective="Produce a domain-neutral result"),
        tasks=[
            PlannedTask(
                task_id="TASK-001",
                title="Research",
                description="Gather evidence",
                task_type="research",
                required_capabilities=["research"],
                acceptance_criteria=["Evidence exists"],
            ),
            PlannedTask(
                task_id="TASK-002",
                title="Create",
                description="Create result",
                task_type="creation",
                depends_on=["TASK-001"],
                acceptance_criteria=["Result exists"],
            ),
        ],
        deliverables=[Deliverable("DEL-001", "Result")],
    )


def test_dispatcher_releases_dependencies_and_selects_generalist_agents() -> None:
    dispatcher = TaskDispatcher()
    task_plan = plan()
    run = dispatcher.initialize(task_plan)

    first = dispatcher.next_ready(task_plan, run)
    assert first is not None
    assert first.task_id == "TASK-001"
    assert dispatcher.select_agent(first)[0] == "researcher_agent"

    dispatcher.transition(
        task_plan, run, first.task_id, "assigned", assigned_agent="researcher_agent"
    )
    dispatcher.transition(task_plan, run, first.task_id, "running")
    dispatcher.transition(task_plan, run, first.task_id, "completed", result="evidence")

    assert dispatcher.next_ready(task_plan, run).task_id == "TASK-002"  # type: ignore[union-attr]
    assert run.tasks[1].status == "ready"


def test_dispatcher_completes_sequential_run_and_repository_round_trips(tmp_path) -> None:
    dispatcher = TaskDispatcher()
    task_plan = plan()
    run = dispatcher.initialize(task_plan)
    repository = FileTaskRunRepository("runs", repository_root=tmp_path)

    for task in task_plan.tasks:
        agent, reason = dispatcher.select_agent(task)
        dispatcher.transition(
            task_plan, run, task.task_id, "assigned", assigned_agent=agent, selection_reason=reason
        )
        dispatcher.transition(task_plan, run, task.task_id, "running")
        dispatcher.transition(task_plan, run, task.task_id, "completed", result={"ok": True})
        repository.save(run)

    restored = repository.get(run.run_id)
    assert run.status == "completed"
    assert restored == run
    assert restored.tasks[1].assigned_agent == "executor_agent"  # type: ignore[union-attr]


def test_failed_task_blocks_dependents() -> None:
    dispatcher = TaskDispatcher()
    task_plan = plan()
    run = dispatcher.initialize(task_plan)
    dispatcher.transition(task_plan, run, "TASK-001", "assigned")
    dispatcher.transition(task_plan, run, "TASK-001", "running")
    dispatcher.transition(task_plan, run, "TASK-001", "failed", error="boom")

    assert run.status == "failed"
    assert run.tasks[1].status == "blocked"


def test_execution_contract_projects_task_run() -> None:
    dispatcher = TaskDispatcher()
    run = dispatcher.initialize(plan())
    contract = map_adk_execution(
        session={"session_id": "session-dispatch", "state": {"task_run": run.to_dict()}},
        events=[],
        objective="Produce a domain-neutral result",
        final_response="",
        settings=OrchestratorSettings(),
    )

    assert contract.task_run is not None
    assert contract.task_run["run_id"] == run.run_id
    assert contract.task_run["tasks"][0]["status"] == "ready"
    assert contract.task_run["schema_version"] == "orchestrator.task_run.v2"


@pytest.mark.parametrize(
    ("strategy", "expected_kind", "expected_node"),
    [
        ("single_agent", "agent", "researcher_agent"),
        ("sequential", "workflow", "sequential"),
        ("parallel", "workflow", "parallel"),
        ("review_critic", "workflow", "review_critic"),
        ("iterative_refinement", "workflow", "iterative_refinement"),
        ("human_in_the_loop", "workflow", "human_in_the_loop"),
        ("verification", "workflow", "review_critic"),
    ],
)
def test_dispatcher_resolves_every_task_strategy(
    strategy: str,
    expected_kind: str,
    expected_node: str,
) -> None:
    task = PlannedTask(
        task_id="TASK-STRATEGY",
        title="Apply strategy",
        description="Exercise one execution strategy",
        task_type="research",
        required_capabilities=["research"],
        acceptance_criteria=["Strategy is resolved"],
        strategy=strategy,  # type: ignore[arg-type]
    )

    selection = TaskDispatcher().select_execution(task)

    assert selection.strategy == strategy
    assert selection.node_kind == expected_kind
    assert selection.node_key == expected_node
    assert selection.assigned_agent == "researcher_agent"


def test_approval_and_review_flags_override_unsafe_simple_strategies() -> None:
    base = PlannedTask(
        task_id="TASK-POLICY",
        title="Policy task",
        description="Exercise policy override",
        task_type="creation",
        acceptance_criteria=["Policy is applied"],
    )
    approval = PlannedTask(**{**base.__dict__, "requires_approval": True})
    review = PlannedTask(**{**base.__dict__, "requires_review": True})

    assert TaskDispatcher().select_execution(approval).strategy == "human_in_the_loop"
    assert TaskDispatcher().select_execution(review).strategy == "review_critic"


def test_strategy_dispatcher_runs_existing_workflows_without_removing_them(tmp_path) -> None:
    task_plan = TaskPlan(
        plan_id="PLAN-STRATEGIES",
        status="validated",
        goal=Goal(objective="Run strategy workflows"),
        tasks=[
            PlannedTask(
                task_id=f"TASK-{index:03d}",
                title=strategy,
                description=f"Run {strategy}",
                task_type="creation",
                depends_on=[] if index == 1 else [f"TASK-{index - 1:03d}"],
                acceptance_criteria=["Completed"],
                strategy=strategy,  # type: ignore[arg-type]
            )
            for index, strategy in enumerate(STRATEGY_WORKFLOWS, start=1)
        ],
        deliverables=[Deliverable("DEL-STRATEGIES", "Strategy results")],
    )
    settings = OrchestratorSettings(
        workspace_enabled=False,
        task_run_root="runs",
    )
    node = create_task_dispatcher_node(settings, repository_root=tmp_path)
    called: list[tuple[str, str]] = []

    class FakeContext:
        state = {
            "task_plan": task_plan.to_dict(),
            "selected_workflow": "sequential",
            "context_package": ContextPackage(
                context_id="CTX-STRATEGIES",
                objective=task_plan.goal.objective,
                workstream=Workstream("WS-STRATEGIES", "Strategies", "Strategy tests"),
            ).to_dict(),
        }

        async def run_node(self, target, *, node_input, run_id):
            import inspect

            from google.adk.agents.context import Context

            inspect.signature(Context.run_node).bind(
                self, target, node_input=node_input, run_id=run_id
            )
            called.append((target.name, run_id))
            return {"target": target.name}

    result = asyncio.run(node._func(ctx=FakeContext(), node_input="objective"))
    didactic = create_phase2_workflows(settings)

    assert result["status"] == "completed"
    assert [target for target, _ in called if target != "replan_guard_agent"] == [
        didactic[key].name for key in STRATEGY_WORKFLOWS.values()
    ]
    assert set(didactic) >= set(STRATEGY_WORKFLOWS.values())

@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_repository_retries_windows_replace_lock(tmp_path, monkeypatch, winerror):
    from orchestrator.dispatching import repository as module

    repository = FileTaskRunRepository("runs", repository_root=tmp_path)
    run = TaskDispatcher().initialize(plan())
    target = repository.save(run)
    original_replace = module.os.replace
    calls = []
    delays = []

    def locked_replace(source, destination):
        calls.append(source)
        if len(calls) < 3:
            error = PermissionError("file temporarily locked")
            error.winerror = winerror
            raise error
        original_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", locked_replace)
    monkeypatch.setattr(module.time, "sleep", delays.append)
    run.status = "completed"
    assert repository.save(run) == target
    assert repository.get(run.run_id) == run
    assert delays == [0.05, 0.1]
    assert not list(target.parent.glob("*.tmp"))


@pytest.mark.parametrize("winerror, attempts", [(5, 6), (None, 1)])
def test_repository_preserves_previous_state_on_replace_failure(
    tmp_path, monkeypatch, winerror, attempts
):
    from orchestrator.dispatching import repository as module

    repository = FileTaskRunRepository("runs", repository_root=tmp_path)
    run = TaskDispatcher().initialize(plan())
    target = repository.save(run)
    previous = target.read_bytes()
    calls = []
    error = PermissionError("persistent access denial")
    if winerror is not None:
        error.winerror = winerror

    def denied_replace(source, destination):
        calls.append(source)
        raise error

    monkeypatch.setattr(module.os, "replace", denied_replace)
    monkeypatch.setattr(module.time, "sleep", lambda delay: None)
    run.status = "completed"
    with pytest.raises(PermissionError) as caught:
        repository.save(run)
    assert caught.value is error
    assert len(calls) == attempts
    assert target.read_bytes() == previous
    assert not list(target.parent.glob("*.tmp"))
