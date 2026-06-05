from __future__ import annotations

import os

from orchestrator.adk_compat import is_adk_installed
from orchestrator.agents import PHASE_2_WORKFLOW_NAMES
from orchestrator.config import (
    OrchestratorSettings,
    ProgressiveMultiAgentResponseSettings,
)
from orchestrator.contracts import AgentHelpRequest, AgentHelpResponse, AgentVisibleResponse
from orchestrator.policies import BudgetPolicy
from orchestrator.tools import capture_objective, get_orchestrator_status, request_human_approval


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("ADK_APP_NAME", "custom-app")
    monkeypatch.setenv("ADK_USER_ID", "user-123")
    monkeypatch.setenv("ADK_MODEL", "gemini-test-model")

    settings = OrchestratorSettings.from_env()

    assert settings.app_name == "custom-app"
    assert settings.user_id == "user-123"
    assert settings.model == "gemini-test-model"


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
    assert [agent.name for agent in workflows["sequential"].sub_agents] == [
        "sequential_planner_agent",
        "sequential_executor_agent",
        "sequential_critic_agent",
        "sequential_summarizer_agent",
    ]
    assert workflows["parallel"].name == "parallel_workflow"
    assert [agent.name for agent in workflows["parallel"].sub_agents] == [
        "parallel_specialists_agent",
        "parallel_summarizer_agent",
    ]
    assert [agent.name for agent in workflows["parallel"].sub_agents[0].sub_agents] == [
        "parallel_planner_agent",
        "parallel_researcher_agent",
        "parallel_executor_agent",
    ]
    assert workflows["review_critic"].max_iterations == BudgetPolicy().max_iterations
    assert workflows["iterative_refinement"].max_iterations == BudgetPolicy().max_iterations
    assert workflows["human_in_the_loop"].sub_agents[1].name == "human_approval_agent"
    assert workflows["agent_help_request"].name == "agent_help_request_workflow"
    assert workflows["progressive_multi_agent_response"].name == (
        "progressive_multi_agent_response_workflow"
    )
    assert [agent.name for agent in workflows["agent_help_request"].sub_agents] == [
        "agent_help_task_owner_agent",
        "agent_help_request_broker_agent",
        "agent_help_provider_agent",
        "agent_help_response_broker_agent",
        "agent_help_task_finalizer_agent",
    ]
    assert [agent.name for agent in workflows["progressive_multi_agent_response"].sub_agents] == [
        "progressive_agent_a",
        "progressive_agent_b",
        "progressive_agent_c",
        "progressive_response_publisher_agent",
    ]
    assert workflows["progressive_multi_agent_response"].sub_agents[-1].output_key == (
        "progressive_agent_responses"
    )


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

    assert [agent.name for agent in workflow.sub_agents] == [
        "progressive_agent_a",
        "progressive_agent_b",
        "progressive_agent_c",
        "progressive_response_publisher_agent",
    ]
    assert "response_chain_summarizer_agent" not in {agent.name for agent in workflow.sub_agents}
    assert workflow.sub_agents[-1].output_key == "progressive_agent_responses"


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

    assert [agent.name for agent in workflow.sub_agents] == [
        "progressive_agent_a",
        "progressive_agent_b",
        "progressive_agent_c",
        "progressive_response_publisher_agent",
        "response_chain_summarizer_agent",
    ]
    assert workflow.sub_agents[-1].output_key == "progressive_final_response"
    assert "final_summarizer_enabled=enabled" in workflow.sub_agents[-1].instruction
    assert "summarizer_response" in workflow.sub_agents[-1].instruction


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

    assert workflow.sub_agents[-1].name == "response_chain_summarizer_agent"
    assert workflow.sub_agents[-1].output_key == "progressive_final_response"
    assert "final_summarizer_enabled=auto" in workflow.sub_agents[-1].instruction
    assert "ponto de decisão do root" in workflow.sub_agents[-1].instruction
    assert "root_selected_response" in workflow.sub_agents[-1].instruction


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
    assert [agent.name for agent in root_agent.sub_agents] == [
        "sequential_workflow",
        "parallel_workflow",
        "review_critic_workflow",
        "iterative_refinement_workflow",
        "human_in_the_loop_workflow",
        "agent_help_request_workflow",
        "progressive_multi_agent_response_workflow",
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
