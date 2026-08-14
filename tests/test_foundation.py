from __future__ import annotations

import os
from types import SimpleNamespace

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
    monkeypatch.setenv("ADK_MODEL_RETRY_ATTEMPTS", "5")
    monkeypatch.setenv("ADK_MODEL_RETRY_INITIAL_DELAY_SECONDS", "0.5")
    monkeypatch.setenv("ADK_MODEL_RETRY_MAX_DELAY_SECONDS", "12")

    settings = OrchestratorSettings.from_env()

    assert settings.app_name == "custom-app"
    assert settings.user_id == "user-123"
    assert settings.model == "gemini-test-model"
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
        "progressive_agent_a",
        "progressive_agent_b",
        "progressive_agent_c",
        "progressive_response_publisher_agent",
    ]
    assert progressive_nodes[-1].output_key == "progressive_agent_responses"


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
        "progressive_agent_a",
        "progressive_agent_b",
        "progressive_agent_c",
        "progressive_response_publisher_agent",
    ]
    assert "response_chain_summarizer_agent" not in {agent.name for agent in nodes}
    assert nodes[-1].output_key == "progressive_agent_responses"


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
        "progressive_agent_a",
        "progressive_agent_b",
        "progressive_agent_c",
        "progressive_response_publisher_agent",
        "response_chain_summarizer_agent",
    ]
    assert nodes[-1].output_key == "progressive_final_response"
    assert "final_summarizer_enabled=enabled" in nodes[-1].instruction
    assert "summarizer_response" in nodes[-1].instruction


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

    finalizer = _workflow_nodes(workflow)[-1]
    assert finalizer.name == "response_chain_summarizer_agent"
    assert finalizer.output_key == "progressive_final_response"
    assert "final_summarizer_enabled=auto" in finalizer.instruction
    assert "ponto de decisão do root" in finalizer.instruction
    assert "root_selected_response" in finalizer.instruction


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

    selected = route_node._func(ctx=ctx, node_input="Use parallel for independent research.")

    assert selected == "parallel"
    assert ctx.state["selected_workflow"] == "parallel"
    assert ctx.state["workflow"] == "parallel"
    assert "parallel" not in ctx.state["workflow_alternatives"]


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
