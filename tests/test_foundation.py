from __future__ import annotations

import os

from orchestrator.adk_compat import is_adk_installed
from orchestrator.agents import PHASE_2_WORKFLOW_NAMES
from orchestrator.config import OrchestratorSettings
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
    assert status["phase"] == "phase_2_adk_workflows"
    assert "root_agent" in status["capabilities"]
    assert "in_memory_session_service" in status["capabilities"]
    assert "sequential_workflow" in status["capabilities"]
    assert "human_in_the_loop_workflow" in status["capabilities"]


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
    assert len(workflows["parallel"].sub_agents) == 3
    assert workflows["review_critic"].max_iterations == BudgetPolicy().max_iterations
    assert workflows["iterative_refinement"].max_iterations == BudgetPolicy().max_iterations
    assert workflows["human_in_the_loop"].sub_agents[1].name == "human_approval_agent"


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
    ]
