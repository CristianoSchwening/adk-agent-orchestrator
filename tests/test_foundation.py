from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from orchestrator.adk_compat import is_adk_installed
from orchestrator.agents import PHASE_2_WORKFLOW_NAMES
from orchestrator.config import (
    OrchestratorSettings,
    ProgressiveMultiAgentResponseSettings,
)
from orchestrator.contracts import AgentHelpRequest, AgentHelpResponse, AgentVisibleResponse
from orchestrator.policies import BudgetPolicy
from orchestrator.tools import capture_objective, get_orchestrator_status, request_human_approval


def _workflow_nodes(workflow):
    return [node for node in workflow.graph.nodes if node.name != "__START__"]


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("ADK_APP_NAME", "custom-app")
    monkeypatch.setenv("ADK_USER_ID", "user-123")
    monkeypatch.setenv("ADK_MODEL", "gemini-test-model")
    monkeypatch.setenv("ADK_MODEL_ROUTER", "gemini-router")
    monkeypatch.setenv("ADK_MODEL_REASONING", "gemini-reasoning")
    monkeypatch.setenv("ADK_MODEL_WORKER", "gemini-worker")
    monkeypatch.setenv("ADK_MODEL_FINALIZER", "gemini-finalizer")
    monkeypatch.setenv("ADK_MODEL_FALLBACK", "gemini-fallback")
    monkeypatch.setenv("ADK_MODEL_RETRY_ATTEMPTS", "5")
    monkeypatch.setenv("ADK_MODEL_RETRY_INITIAL_DELAY_SECONDS", "0.5")
    monkeypatch.setenv("ADK_MODEL_RETRY_MAX_DELAY_SECONDS", "12")

    settings = OrchestratorSettings.from_env()

    assert settings.app_name == "custom-app"
    assert settings.user_id == "user-123"
    assert settings.model == "gemini-test-model"
    assert settings.resolved_model_basket() == {
        "router": "gemini-router",
        "reasoning": "gemini-reasoning",
        "worker": "gemini-worker",
        "finalizer": "gemini-finalizer",
        "fallback": "gemini-fallback",
    }
    assert settings.model_retry_attempts == 5
    assert settings.model_retry_initial_delay_seconds == 0.5
    assert settings.model_retry_max_delay_seconds == 12


def test_gemini_model_uses_bounded_transient_retry_policy():
    if not is_adk_installed():
        return

    from orchestrator.model import TRANSIENT_HTTP_STATUS_CODES, create_gemini_model

    model = create_gemini_model(
        OrchestratorSettings(
            model="gemini-flash-latest",
            model_retry_attempts=4,
            model_retry_initial_delay_seconds=1.0,
            model_retry_max_delay_seconds=8.0,
            model_retry_exponential_base=2.0,
            model_retry_jitter_seconds=1.0,
        )
    )

    assert model.model == "gemini-flash-latest"
    assert model.retry_options.attempts == 4
    assert model.retry_options.initial_delay == 1.0
    assert model.retry_options.max_delay == 8.0
    assert model.retry_options.exp_base == 2.0
    assert model.retry_options.jitter == 1.0
    assert model.retry_options.http_status_codes == TRANSIENT_HTTP_STATUS_CODES


def test_model_basket_falls_back_to_global_model():
    settings = OrchestratorSettings(model="gemini-global", router_model="gemini-router")

    assert settings.model_for("router") == "gemini-router"
    assert settings.model_for("reasoning") == "gemini-global"
    assert settings.model_for("worker") == "gemini-global"
    assert settings.model_for("finalizer") == "gemini-global"
    assert settings.resolved_model_basket()["fallback"] is None


def test_daily_quota_falls_back_and_opens_primary_circuit():
    from orchestrator.model import _with_fallback, reset_model_fallback_circuits

    class FakePrimary:
        model = "gemini-primary"

        def __init__(self):
            self.calls = 0

        async def generate_content_async(self, llm_request, stream=False):
            self.calls += 1
            raise RuntimeError(
                "429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier"
            )
            yield  # pragma: no cover

    class FakeFallback:
        model = "gemini-lite"

        def __init__(self):
            self.requested_models = []

        async def generate_content_async(self, llm_request, stream=False):
            self.requested_models.append(llm_request.model)
            yield SimpleNamespace(custom_metadata=None)

    async def collect(model):
        request = SimpleNamespace(model=None)
        return [item async for item in model.generate_content_async(request)]

    reset_model_fallback_circuits()
    primary = FakePrimary()
    fallback = FakeFallback()
    model = _with_fallback(primary, fallback, role="router")

    first = asyncio.run(collect(model))
    second = asyncio.run(collect(model))

    assert primary.calls == 1
    assert first[0].custom_metadata["model_routing"] == {
        "role": "router",
        "requested_model": "gemini-primary",
        "used_model": "gemini-lite",
        "fallback_used": True,
        "fallback_reason": "daily_quota_exhausted",
    }
    assert second[0].custom_metadata["model_routing"]["fallback_reason"] == (
        "daily_quota_circuit_open"
    )
    assert fallback.requested_models == ["gemini-lite", "gemini-lite"]
    reset_model_fallback_circuits()


def test_non_transient_model_error_does_not_fallback():
    from orchestrator.model import _with_fallback, reset_model_fallback_circuits

    class FakePrimary:
        model = "gemini-primary"

        async def generate_content_async(self, llm_request, stream=False):
            raise RuntimeError("400 INVALID_ARGUMENT")
            yield  # pragma: no cover

    class FakeFallback:
        model = "gemini-lite"

        async def generate_content_async(self, llm_request, stream=False):
            raise AssertionError("fallback must not run")
            yield  # pragma: no cover

    async def collect(model):
        request = SimpleNamespace(model=None)
        return [item async for item in model.generate_content_async(request)]

    reset_model_fallback_circuits()
    model = _with_fallback(FakePrimary(), FakeFallback(), role="reasoning")

    try:
        asyncio.run(collect(model))
    except RuntimeError as exc:
        assert "INVALID_ARGUMENT" in str(exc)
    else:
        raise AssertionError("expected primary model error")


def test_agents_use_role_specific_models():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_phase2_workflows, create_root_agent

    settings = OrchestratorSettings(
        model="gemini-global",
        router_model="gemini-router",
        reasoning_model="gemini-reasoning",
        worker_model="gemini-worker",
        finalizer_model="gemini-finalizer",
    )
    workflows = create_phase2_workflows(settings)
    root = create_root_agent(settings)

    root_models = {
        node.name: node.model.model
        for node in _workflow_nodes(root)
        if hasattr(node, "model")
    }
    sequential_models = {
        node.name: node.model.model
        for node in _workflow_nodes(workflows["sequential"])
        if hasattr(node, "model")
    }
    help_models = {
        node.name: node.model.model
        for node in _workflow_nodes(workflows["agent_help_request"])
        if hasattr(node, "model")
    }

    assert root_models["workflow_router_agent"] == "gemini-router"
    assert root_models["task_planner_agent"] == "gemini-reasoning"
    assert sequential_models == {
        "sequential_planner_agent": "gemini-worker",
        "sequential_executor_agent": "gemini-worker",
        "sequential_critic_agent": "gemini-reasoning",
        "sequential_summarizer_agent": "gemini-finalizer",
    }
    assert help_models["agent_help_task_owner_agent"] == "gemini-reasoning"
    assert help_models["agent_help_request_broker_agent"] == "gemini-worker"
    assert help_models["agent_help_provider_agent"] == "gemini-worker"
    assert help_models["agent_help_response_broker_agent"] == "gemini-worker"
    assert help_models["agent_help_task_finalizer_agent"] == "gemini-finalizer"


def test_all_llm_agents_receive_retrying_gemini_model():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_phase2_workflows, create_root_agent

    settings = OrchestratorSettings(model="gemini-flash-latest", model_retry_attempts=3)
    workflows = create_phase2_workflows(settings)
    root = create_root_agent(settings)
    agents = [
        node
        for workflow in workflows.values()
        for node in _workflow_nodes(workflow)
        if hasattr(node, "model")
    ]
    agents.extend(node for node in _workflow_nodes(root) if hasattr(node, "model"))

    assert agents
    assert all(agent.model.retry_options.attempts == 3 for agent in agents)


def test_tools_return_structured_payloads():
    captured = capture_objective("  Criar uma fundação ADK  ")
    status = get_orchestrator_status()

    assert captured["status"] == "success"
    assert captured["objective"] == "Criar uma fundação ADK"
    assert status["phase"] == "phase_5_evaluation_production"
    assert "root_agent" in status["capabilities"]
    assert "in_memory_session_service" in status["capabilities"]
    assert "sequential_workflow" in status["capabilities"]
    assert "human_in_the_loop_workflow" in status["capabilities"]
    assert "agent_help_request_workflow" in status["capabilities"]
    assert "progressive_multi_agent_response_workflow" in status["capabilities"]
    assert "tool_catalog" in status["capabilities"]
    assert "mcp_toolset_factory" in status["capabilities"]


def test_budget_policy_boundaries():
    policy = BudgetPolicy(max_iterations=2, max_model_calls=3, max_elapsed_ms=1_000)

    assert policy.should_continue(iterations=1, model_calls=2, elapsed_ms=999)
    assert not policy.should_continue(iterations=2, model_calls=2, elapsed_ms=999)
    assert not policy.should_continue(iterations=1, model_calls=3, elapsed_ms=999)
    assert not policy.should_continue(iterations=1, model_calls=2, elapsed_ms=1_000)


def test_human_approval_tool_returns_structured_decision():
    decision = request_human_approval(
        decision="approved",
        rationale="  riscos aceitos  ",
        requested_action="  prosseguir com implantação  ",
    )

    assert decision["status"] == "recorded"
    assert decision["approved"] is True
    assert decision["rationale"] == "riscos aceitos"
    assert decision["requested_action"] == "prosseguir com implantação"


def test_phase2_workflows_can_be_created_when_adk_is_installed():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_phase2_workflows

    workflows = create_phase2_workflows(OrchestratorSettings(model="gemini-flash-latest"))

    assert tuple(workflows) == PHASE_2_WORKFLOW_NAMES
    assert workflows["sequential"].name == "sequential_workflow"
    assert [agent.name for agent in _workflow_nodes(workflows["sequential"])] == [
        "sequential_planner_agent",
        "sequential_executor_agent",
        "sequential_critic_agent",
        "sequential_summarizer_agent",
    ]
    assert workflows["parallel"].name == "parallel_workflow"
    assert [agent.name for agent in _workflow_nodes(workflows["parallel"])] == [
        "parallel_planner_agent",
        "parallel_researcher_agent",
        "parallel_executor_agent",
        "parallel_specialists_join",
        "parallel_summarizer_agent",
    ]
    assert "review_critic_gate" in {
        node.name for node in _workflow_nodes(workflows["review_critic"])
    }
    assert "iterative_refinement_gate" in {
        node.name for node in _workflow_nodes(workflows["iterative_refinement"])
    }
    assert _workflow_nodes(workflows["human_in_the_loop"])[1].name == "human_approval_agent"
    assert workflows["agent_help_request"].name == "agent_help_request_workflow"
    assert workflows["progressive_multi_agent_response"].name == (
        "progressive_multi_agent_response_workflow"
    )
    assert [agent.name for agent in _workflow_nodes(workflows["agent_help_request"])] == [
        "agent_help_task_owner_agent",
        "agent_help_request_broker_agent",
        "agent_help_provider_agent",
        "agent_help_response_broker_agent",
        "agent_help_task_finalizer_agent",
    ]
    progressive_nodes = _workflow_nodes(workflows["progressive_multi_agent_response"])
    assert [agent.name for agent in progressive_nodes] == [
        "progressive_role_router_agent",
        "progressive_agent_a",
        "progressive_agent_b",
        "publish_progressive_response_a",
        "publish_progressive_response_b",
        "progressive_specialists_join",
        "progressive_requirements_verifier_agent",
        "progressive_agent_c",
        "publish_progressive_response_c",
        "progressive_canonical_finalizer",
    ]


def test_progressive_workflow_without_final_summarizer_when_disabled():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_progressive_multi_agent_response_workflow

    settings = OrchestratorSettings(
        model="gemini-flash-latest",
        progressive_multi_agent_response=ProgressiveMultiAgentResponseSettings(
            final_summarizer_enabled=False,
            final_response_strategy="all_visible_responses",
        ),
    )

    workflow = create_progressive_multi_agent_response_workflow(settings)

    nodes = _workflow_nodes(workflow)
    assert [agent.name for agent in nodes] == [
        "progressive_role_router_agent",
        "progressive_agent_a",
        "progressive_agent_b",
        "publish_progressive_response_a",
        "publish_progressive_response_b",
        "progressive_specialists_join",
        "progressive_requirements_verifier_agent",
        "progressive_agent_c",
        "publish_progressive_response_c",
        "progressive_canonical_finalizer",
    ]
    assert "response_chain_summarizer_agent" not in {agent.name for agent in nodes}


def test_progressive_workflow_adds_final_summarizer_when_enabled():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_progressive_multi_agent_response_workflow

    settings = OrchestratorSettings(
        model="gemini-flash-latest",
        progressive_multi_agent_response=ProgressiveMultiAgentResponseSettings(
            final_summarizer_enabled=True,
            final_response_strategy="summarizer_response",
        ),
    )

    workflow = create_progressive_multi_agent_response_workflow(settings)

    nodes = _workflow_nodes(workflow)
    assert [agent.name for agent in nodes] == [
        "progressive_role_router_agent",
        "progressive_agent_a",
        "progressive_agent_b",
        "publish_progressive_response_a",
        "publish_progressive_response_b",
        "progressive_specialists_join",
        "progressive_requirements_verifier_agent",
        "progressive_agent_c",
        "publish_progressive_response_c",
        "response_chain_summarizer_agent",
        "progressive_canonical_finalizer",
    ]
    assert nodes[-2].output_key == "progressive_final_response"
    assert "final_summarizer_enabled=enabled" in nodes[-2].instruction
    assert "summarizer_response" in nodes[-2].instruction


def test_progressive_publish_nodes_materialize_each_response_incrementally():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_progressive_multi_agent_response_workflow

    workflow = create_progressive_multi_agent_response_workflow(
        OrchestratorSettings(workspace_enabled=False)
    )
    nodes = {node.name: node for node in _workflow_nodes(workflow)}
    state = {}
    ctx = SimpleNamespace(state=state)

    state["progressive_response_a"] = '{"content":"Primeira contribuição"}'
    nodes["publish_progressive_response_a"]._func(ctx=ctx, node_input="ignored")
    assert [item["response_id"] for item in state["progressive_agent_responses"]] == [
        "response-x"
    ]

    state["progressive_response_b"] = '{"content":"Segunda contribuição"}'
    nodes["publish_progressive_response_b"]._func(ctx=ctx, node_input="ignored")
    assert [item["response_id"] for item in state["progressive_agent_responses"]] == [
        "response-x",
        "response-z",
    ]

    state["progressive_response_c"] = '{"content":"Síntese"}'
    nodes["publish_progressive_response_c"]._func(ctx=ctx, node_input="ignored")
    responses = state["progressive_agent_responses"]
    assert [item["response_id"] for item in responses] == [
        "response-x",
        "response-z",
        "response-c",
    ]
    assert responses[1]["depends_on_response_ids"] == []
    assert responses[2]["depends_on_response_ids"] == ["response-x", "response-z"]
    assert all(item["metadata"]["published_incrementally"] for item in responses)


def test_progressive_canonical_finalizer_emits_plain_synthesis_content():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_progressive_multi_agent_response_workflow

    workflow = create_progressive_multi_agent_response_workflow(
        OrchestratorSettings(workspace_enabled=False)
    )
    nodes = {node.name: node for node in _workflow_nodes(workflow)}
    ctx = SimpleNamespace(state={})
    nested = json.dumps(
        {
            "content": json.dumps(
                {
                    "response_id": "response-c",
                    "agent_name": "progressive_agent_c",
                    "content": "Síntese final auditada",
                }
            )
        }
    )

    result = nodes["progressive_canonical_finalizer"]._func(
        ctx=ctx,
        node_input=nested,
    )

    assert result == "Síntese final auditada"
    assert ctx.state["progressive_canonical_final_response"] == result


def test_progressive_workflow_fans_out_independent_specialists_before_join():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_progressive_multi_agent_response_workflow

    workflow = create_progressive_multi_agent_response_workflow(
        OrchestratorSettings(workspace_enabled=False)
    )
    edge_pairs = {
        (edge.from_node.name, edge.to_node.name) for edge in workflow.graph.edges
    }

    assert ("__START__", "progressive_role_router_agent") in edge_pairs
    assert ("progressive_role_router_agent", "progressive_agent_a") in edge_pairs
    assert ("progressive_role_router_agent", "progressive_agent_b") in edge_pairs
    assert (
        "publish_progressive_response_a",
        "progressive_specialists_join",
    ) in edge_pairs
    assert (
        "publish_progressive_response_b",
        "progressive_specialists_join",
    ) in edge_pairs
    assert (
        "progressive_specialists_join",
        "progressive_requirements_verifier_agent",
    ) in edge_pairs
    assert (
        "progressive_requirements_verifier_agent",
        "progressive_agent_c",
    ) in edge_pairs
    assert (
        "publish_progressive_response_c",
        "progressive_canonical_finalizer",
    ) in edge_pairs

    nodes = {node.name: node for node in _workflow_nodes(workflow)}
    assert 'depends_on_response_ids=[]' in nodes["progressive_agent_b"].instruction
    assert "progressive_response_a" in nodes["progressive_agent_b"].instruction
    assert "specialist_a" in nodes["progressive_role_router_agent"].instruction
    assert "specialist_b" in nodes["progressive_role_router_agent"].instruction
    assert "calculation_audit" in nodes[
        "progressive_requirements_verifier_agent"
    ].instruction
    assert "corrections_required" in nodes["progressive_agent_c"].instruction


def test_progressive_workflow_auto_mode_lets_root_decide_finalization():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_progressive_multi_agent_response_workflow

    settings = OrchestratorSettings(
        model="gemini-flash-latest",
        progressive_multi_agent_response=ProgressiveMultiAgentResponseSettings(
            final_summarizer_enabled="auto",
            final_response_strategy="root_selected_response",
        ),
    )

    workflow = create_progressive_multi_agent_response_workflow(settings)

    nodes = _workflow_nodes(workflow)
    finalizer = nodes[-2]
    assert finalizer.name == "response_chain_summarizer_agent"
    assert finalizer.output_key == "progressive_final_response"
    assert "final_summarizer_enabled=auto" in finalizer.instruction
    assert "ponto de decisão do root" in finalizer.instruction
    assert "root_selected_response" in finalizer.instruction
    assert nodes[-1].name == "progressive_canonical_finalizer"


def test_progressive_workflow_settings_from_env(monkeypatch):
    monkeypatch.setenv("ADK_PROGRESSIVE_FINAL_SUMMARIZER_ENABLED", "auto")
    monkeypatch.setenv("ADK_PROGRESSIVE_FINAL_RESPONSE_STRATEGY", "root_selected_response")

    settings = OrchestratorSettings.from_env()

    assert settings.progressive_multi_agent_response.final_summarizer_enabled == "auto"
    assert settings.progressive_multi_agent_response.final_response_strategy == (
        "root_selected_response"
    )


def test_agent_help_contracts_are_serializable():
    request = AgentHelpRequest(
        request_id="help-1",
        requester_agent="planner_agent",
        provider_agent="researcher_agent",
        requested_capability="evidence_check",
        reason="Need current supporting context.",
        payload={"question": "What evidence supports the plan?"},
        metadata={"help_needed": True},
    )
    response = AgentHelpResponse(
        request_id=request.request_id,
        requester_agent=request.requester_agent,
        provider_agent=request.provider_agent,
        requested_capability=request.requested_capability,
        reason=request.reason,
        payload=request.payload,
        response={"summary": "Evidence is sufficient."},
        metadata={"brokered": True},
    )

    assert request.to_dict()["status"] == "requested"
    assert request.to_dict()["response"] is None
    assert response.to_dict()["status"] == "completed"
    assert response.to_dict()["request_id"] == "help-1"


def test_agent_visible_response_contract_is_serializable():
    response = AgentVisibleResponse(
        response_id="response-c",
        agent_name="progressive_agent_c",
        agent_role="synthesis_specialist",
        content="Síntese baseada nas contribuições anteriores.",
        depends_on_response_ids=["response-x", "response-z"],
        publication_order=3,
        created_at="2026-05-30T00:00:01+00:00",
        metadata={"workflow": "progressive_multi_agent_response"},
    )

    payload = response.to_dict()

    assert payload["response_id"] == "response-c"
    assert payload["depends_on_response_ids"] == ["response-x", "response-z"]
    assert payload["visibility"] == "user_visible"
    assert payload["status"] == "published"


def test_adk_installation_probe_is_boolean():
    assert isinstance(is_adk_installed(), bool)


def test_root_agent_can_be_created_when_adk_is_installed():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_root_agent

    settings = OrchestratorSettings(model=os.getenv("ADK_MODEL", "gemini-flash-latest"))
    root_agent = create_root_agent(settings)

    assert root_agent.name == "root_orchestrator_agent"
    assert [agent.name for agent in _workflow_nodes(root_agent)] == [
        "task_planner_agent",
        "normalize_task_plan",
        "workflow_router_agent",
        "normalize_workflow_route",
        "sequential_workflow",
        "parallel_workflow",
        "review_critic_workflow",
        "iterative_refinement_workflow",
        "human_in_the_loop_workflow",
        "agent_help_request_workflow",
        "progressive_multi_agent_response_workflow",
    ]


def test_root_route_node_persists_workflow_decision_when_adk_is_installed():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_root_agent

    root = create_root_agent(OrchestratorSettings(workspace_enabled=False))
    route_node = next(node for node in root.graph.nodes if node.name == "normalize_workflow_route")
    ctx = SimpleNamespace(state={})

    selected = route_node._func(
        ctx=ctx,
        node_input={
            "selected_workflow": "parallel",
            "rationale": "The research tasks are independent.",
        },
    )

    assert selected == "parallel"
    assert ctx.state["selected_workflow"] == "parallel"
    assert ctx.state["workflow"] == "parallel"
    assert ctx.state["workflow_selection_source"] == "model"
    assert ctx.state["decision_rationale"] == "The research tasks are independent."
    assert "parallel" not in ctx.state["workflow_alternatives"]


def test_root_route_node_rejects_fuzzy_or_unknown_routes_when_adk_is_installed():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_root_agent

    root = create_root_agent(OrchestratorSettings(workspace_enabled=False))
    route_node = next(node for node in root.graph.nodes if node.name == "normalize_workflow_route")
    ctx = SimpleNamespace(state={})

    with pytest.raises(ValueError, match="invalid structured output"):
        route_node._func(ctx=ctx, node_input="Use parallel for independent research.")
    with pytest.raises(ValueError, match="unsupported workflow"):
        route_node._func(
            ctx=ctx,
            node_input={"selected_workflow": "unknown", "rationale": "Invalid route."},
        )

    assert ctx.state == {}


def test_task_plan_normalizer_persists_validated_plan_when_adk_is_installed():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_root_agent

    root = create_root_agent(OrchestratorSettings(workspace_enabled=False))
    normalizer = next(node for node in root.graph.nodes if node.name == "normalize_task_plan")
    ctx = SimpleNamespace(state={})
    draft = {
        "goal": {
            "objective": "Prepare a reusable proposal",
            "constraints": ["Remain domain neutral"],
            "success_criteria": ["Proposal is actionable"],
        },
        "tasks": [
            {
                "task_id": "TASK-001",
                "title": "Prepare proposal",
                "description": "Create the requested proposal.",
                "task_type": "creation",
                "depends_on": [],
                "required_capabilities": ["synthesis"],
                "acceptance_criteria": ["Proposal satisfies the goal"],
                "strategy": "single_agent",
                "requires_review": False,
                "requires_approval": False,
            }
        ],
        "deliverables": [
            {"deliverable_id": "DEL-001", "description": "Final proposal"}
        ],
        "assumptions": [],
    }

    forwarded = json.loads(normalizer._func(ctx=ctx, node_input=draft))

    assert ctx.state["task_plan_status"] == "validated"
    assert ctx.state["task_plan_source"] == "llm"
    assert ctx.state["task_plan"]["schema_version"] == "orchestrator.task_plan.v1"
    assert forwarded["objective"] == "Prepare a reusable proposal"


def test_explicit_workflow_is_wrapped_by_adk_task_planner_when_installed():
    if not is_adk_installed():
        return

    from orchestrator.agents import create_planned_workflow

    workflow = create_planned_workflow(
        OrchestratorSettings(workspace_enabled=False),
        workflow_name="parallel",
    )

    assert [node.name for node in _workflow_nodes(workflow)] == [
        "task_planner_agent",
        "normalize_task_plan",
        "parallel_workflow",
    ]


def test_specialist_factories_can_be_created_when_adk_is_installed():
    if not is_adk_installed():
        return

    from orchestrator.agents import (
        create_approval_agent,
        create_critic_agent,
        create_executor_agent,
        create_planner_agent,
        create_refiner_agent,
        create_researcher_agent,
        create_summarizer_agent,
    )

    settings = OrchestratorSettings(model=os.getenv("ADK_MODEL", "gemini-flash-latest"))
    specialists = [
        create_planner_agent(settings),
        create_executor_agent(settings),
        create_critic_agent(settings),
        create_summarizer_agent(settings),
        create_researcher_agent(settings),
        create_refiner_agent(settings),
        create_approval_agent(settings),
    ]

    assert [agent.name for agent in specialists] == [
        "planner_agent",
        "executor_agent",
        "critic_agent",
        "summarizer_agent",
        "researcher_agent",
        "refiner_agent",
        "approval_agent",
    ]
