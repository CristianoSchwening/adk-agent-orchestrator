from __future__ import annotations

from orchestrator.config import OrchestratorSettings
from orchestrator.dispatching import FileTaskRunRepository, TaskDispatcher
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
