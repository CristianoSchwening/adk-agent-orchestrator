from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from orchestrator.config import OrchestratorSettings
from orchestrator.context import ContextPackage, Workstream
from orchestrator.human_input import HumanResponse
from orchestrator.planning import Deliverable, Goal, PlannedTask, TaskPlan
from orchestrator.runner.human_runs import HumanRunStore, RunBusyError


def test_human_response_requires_comment_and_store_lock(tmp_path):
    with pytest.raises(ValueError):
        HumanResponse(decision="rejected", comment=" ", idempotency_key="key")
    store = HumanRunStore(tmp_path)
    with store.lock("run"):
        with pytest.raises(RunBusyError), store.lock("run"):
            pass
    with store.lock("run"):
        store.save("run", {"value": "durable"})
    assert HumanRunStore(tmp_path).load("run") == {"value": "durable"}


def test_human_snapshot_survives_windows_reader_lock(tmp_path, monkeypatch):
    from orchestrator.runner import human_runs

    store = HumanRunStore(tmp_path)
    store.save("run", {"candidate": "original"})
    original_replace = human_runs.os.replace
    attempts = []

    def replace(source, target):
        attempts.append(source)
        if len(attempts) == 1:
            error = PermissionError("reader lock")
            error.winerror = 32
            raise error
        original_replace(source, target)

    monkeypatch.setattr(human_runs.os, "replace", replace)
    monkeypatch.setattr(human_runs.time, "sleep", lambda delay: None)
    store.save("run", {"candidate": "revised"})
    assert store.load("run") == {"candidate": "revised"}
    assert len(attempts) == 2
    assert not list(tmp_path.glob("*.tmp"))


def test_durable_sessions_reject_genuine_stale_writer(tmp_path):
    from google.adk.errors._stale_session_error import StaleSessionError
    from google.adk.events import Event

    from orchestrator.runner.bootstrap import _persistent_sessions

    async def exercise():
        service = _persistent_sessions(str(tmp_path / "sessions.sqlite"))
        original = await service.create_session(app_name="stale_test", user_id="test")
        stale = await service.get_session(app_name="stale_test", user_id="test",
                                          session_id=original.id)
        await service.append_event(session=original, event=Event(author="test", output="first"))
        with pytest.raises(StaleSessionError):
            await service.append_event(session=stale, event=Event(author="test", output="second"))
        await service.close()

    asyncio.run(exercise())


def test_dynamic_failure_preserves_actionable_candidate_diagnostic():
    from google.adk.workflow._errors import DynamicNodeFailError

    from orchestrator.errors import execution_error_message

    error = DynamicNodeFailError(message="Dynamic node failed",
                                 error=ValueError("review_candidate_missing"),
                                 error_node_path="review/input")
    assert "review_candidate_missing" in execution_error_message(error)


@pytest.mark.parametrize("decision", ["approved", "rejected", "needs_changes", "clarification"])
def test_api_pauses_and_resumes_same_adk_session(tmp_path, monkeypatch, decision):
    from google.adk.workflow import FunctionNode, Workflow

    from orchestrator import server
    from orchestrator.agents import task_dispatcher, workflows
    from orchestrator.runner import bootstrap

    settings = OrchestratorSettings(workspace_enabled=False, task_run_root="runs",
                                    task_plan_root="plans")
    monkeypatch.setattr(bootstrap, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(server.OrchestratorSettings, "from_env", lambda: settings)
    monkeypatch.setattr(server, "_human_store", lambda settings: HumanRunStore(
        tmp_path / "executions"))
    calls = {"prepare": 0, "followup": 0, "first": 0}
    plan = TaskPlan(
        plan_id="PLAN-HUMAN", status="validated", goal=Goal(objective="Approve a proposal"),
        tasks=[PlannedTask(task_id="TASK-001", title="First", description="Prepare data",
                           task_type="creation", acceptance_criteria=["Data prepared"]),
               PlannedTask(task_id="TASK-002", title="Human", description="Propose next action",
                           task_type="creation", acceptance_criteria=["Human approved"],
                           metadata=({"human_input_kind": "clarification",
                                      "human_question": "Qual é a data desejada?"}
                                     if decision == "clarification" else {}),
                           depends_on=["TASK-001"], requires_approval=True)],
        deliverables=[Deliverable("DEL-001", "Approved proposal")],
    )
    package = ContextPackage(context_id="CTX-HUMAN", objective=plan.goal.objective,
                             workstream=Workstream("WS-HUMAN", "Human", "Tests"))

    def prepare(settings):
        def emit(ctx, node_input):
            calls["prepare"] += 1
            return f"Concrete proposal {calls['prepare']}"
        return FunctionNode(func=emit, name="human_context_agent")

    def followup(settings):
        def emit(ctx, node_input):
            calls["followup"] += 1
            assert node_input["human_response"]["decision"] == "approved"
            return node_input["candidate"]
        return FunctionNode(func=emit, name="human_followup_agent")

    def first(settings, **kwargs):
        def emit(ctx, node_input):
            calls["first"] += 1
            return "Prepared data"
        return FunctionNode(func=emit, name=kwargs["name"])

    def guard(settings):
        def evaluate(ctx, node_input):
            criteria = json.loads(node_input)["acceptance_criteria"]
            return {"trigger": "none", "rationale": "Done", "criteria": [
                {"criterion_id": item["criterion_id"], "status": "passed",
                 "rationale": "Observed", "evidence": "Done"} for item in criteria]}
        return FunctionNode(func=evaluate, name="replan_guard_agent")

    monkeypatch.setattr(workflows, "create_context_agent", prepare)
    monkeypatch.setattr(workflows, "create_followup_agent", followup)
    monkeypatch.setattr(task_dispatcher, "create_executor_agent", first)
    monkeypatch.setattr(task_dispatcher, "create_replan_guard_agent", guard)

    def root(settings):
        def seed(ctx, node_input):
            ctx.state["task_plan"] = plan.to_dict()
            ctx.state["context_package"] = package.to_dict()
            return node_input
        return Workflow(name="test_root", edges=[("START",
            FunctionNode(func=seed, name="seed"),
            task_dispatcher.create_task_dispatcher_node(settings, repository_root=tmp_path))])

    monkeypatch.setattr(bootstrap, "create_root_agent", root)
    with TestClient(server.app) as client:
        started = client.post("/api/run", json={"objective": plan.goal.objective})
        assert started.status_code == 200, started.text
        data = started.json()
        assert data["task"]["status"] == "awaiting_human", data
        assert calls == {"first": 1, "prepare": 1, "followup": 0}
        run_id = data["run_id"]
        request = data["human_requests"][-1]
        assert request["candidate"] == "Concrete proposal 1"
        # Rebuild service/runner from durable SQLite events, as after a restart.
        bootstrap._persistent_sessions.cache_clear()
        assert client.get(f"/api/runs/{run_id}").json() == data
        url = f"/api/runs/{run_id}/human-requests/{request['request_id']}/response"
        answer = {"decision": decision, "comment": "Human feedback", "idempotency_key": "first"}
        store = HumanRunStore(tmp_path / "executions")
        saved = store.load(run_id)
        saved["contract"]["task_plan"]["revision"] += 1
        store.save(run_id, saved)
        assert client.post(url, json=answer).status_code == 409
        saved["contract"]["task_plan"]["revision"] -= 1
        store.save(run_id, saved)
        answered = client.post(url, json=answer)
        assert answered.status_code == 200, answered.text
        updated = answered.json()
        assert updated["task"]["session_id"] == data["task"]["session_id"]
        assert updated["task"]["task_id"] == data["task"]["task_id"]
        assert updated["task"]["created_at"] == data["task"]["created_at"]
        assert updated["task_run"]["run_id"] == data["task_run"]["run_id"]
        assert calls["first"] == 1
        assert updated["task_run"]["tasks"][1]["attempt"] == 1
        assert client.post(url, json=answer).json() == updated
        assert client.post(url, json={**answer, "decision": "rejected"}).status_code == (
            200 if decision == "rejected" else 409)
        unknown_url = url.replace(request["request_id"], "unknown")
        assert client.post(unknown_url, json=answer).status_code == 404
        if decision == "approved":
            assert updated["task"]["status"] == "completed"
            assert calls["followup"] == 1
        elif decision == "rejected":
            assert updated["task"]["status"] == "cancelled"
            assert calls["followup"] == 0
        else:
            assert updated["task"]["status"] == "awaiting_human"
            next_request = updated["human_requests"][-1]
            assert next_request["request_id"] != request["request_id"]
            assert next_request["kind"] == "approval"
            assert next_request["message"] == "Você aprova esta proposta?"
            assert next_request["candidate"] == "Concrete proposal 2"
            next_url = f"/api/runs/{run_id}/human-requests/{next_request['request_id']}/response"
            final = client.post(next_url, json={**answer, "decision": "approved",
                                               "idempotency_key": "second"})
            assert final.status_code == 200, final.text
            assert final.json()["task"]["status"] == "completed"
            assert calls["followup"] == 1
    # Close persistent engines before the temporary test directory is removed.
    asyncio.run(bootstrap._persistent_sessions(str(tmp_path / "executions" / "sessions.sqlite"))
                .db_engine.dispose())


@pytest.mark.parametrize("candidate", ["Primeira candidata concreta", "Outra candidata concreta"])
def test_critic_model_receives_explicit_candidate_and_original_task(monkeypatch, candidate):
    from google.adk import Runner
    from google.adk.agents import LlmAgent
    from google.adk.apps import App
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.adk.sessions import InMemorySessionService
    from google.adk.workflow import FunctionNode
    from google.genai.types import Content, Part
    from pydantic import Field

    from orchestrator.agents import workflows
    from orchestrator.policies import BudgetPolicy

    class CapturingModel(BaseLlm):
        model: str = "deterministic"
        requests: list = Field(default_factory=list)

        async def generate_content_async(self, llm_request, stream=False):
            self.requests.append(llm_request)
            yield LlmResponse(content=Content(role="model", parts=[Part(text="Reviewed")]))

    model = CapturingModel()

    def author_factory(settings, *, name, output_key):
        def author(ctx, node_input):
            ctx.state[output_key] = candidate
            return candidate
        return FunctionNode(func=author, name=name)

    def critic_factory(settings, *, name, output_key):
        return LlmAgent(name=name, model=model, output_key=output_key,
                        include_contents="none", instruction="Review the provided candidate.")

    monkeypatch.setattr(workflows, "create_executor_agent", author_factory)
    monkeypatch.setattr(workflows, "create_critic_agent", critic_factory)
    workflow = workflows.create_review_critic_workflow(
        OrchestratorSettings(workspace_enabled=False), budget_policy=BudgetPolicy(max_iterations=1))

    async def execute():
        app = App(name="critic_context_test", root_agent=workflow)
        sessions = InMemorySessionService()
        runner = Runner(app=app, session_service=sessions)
        session = await sessions.create_session(app_name=app.name, user_id="test")
        async for _ in runner.run_async(user_id="test", session_id=session.id,
                                       new_message=Content(role="user", parts=[Part(
                                           text="Original objective and acceptance criteria")])):
            pass

    asyncio.run(execute())
    assert len(model.requests) == 1
    received = "\n".join(part.text or "" for content in model.requests[0].contents
                         for part in content.parts)
    assert candidate in received
    assert "Original objective and acceptance criteria" in received
    assert '"candidate"' in received
