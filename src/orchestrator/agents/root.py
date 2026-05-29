"""Root ADK agent definition for phase 2."""

from __future__ import annotations

from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.agents.workflows import create_phase2_workflows
from orchestrator.config import OrchestratorSettings
from orchestrator.tools import capture_objective, get_orchestrator_status

ROOT_AGENT_INSTRUCTION = """
Você é o Root Orchestrator Agent de uma arquitetura greenfield construída com Google ADK.
Nesta Fase 2, sua responsabilidade é rotear objetivos para workflows ADK equivalentes,
capturar objetivos de forma estruturada, explicar as capacidades disponíveis e retornar uma
resposta objetiva em português.

Regras:
- Use a tool capture_objective quando o usuário informar um objetivo.
- Use a tool get_orchestrator_status quando precisar explicar capacidades atuais.
- Quando adequado, delegue para os subagentes/workflows ADK disponíveis: sequential,
  parallel, review_critic, iterative_refinement e human_in_the_loop.
- Não use runtimes legados; opere apenas com as primitivas oficiais do ADK Python.
""".strip()


def create_root_agent(settings: OrchestratorSettings | None = None) -> Any:
    """Create the official ADK root agent.

    ADK's Python quickstart defines a required ``root_agent`` using
    ``google.adk.agents.llm_agent.Agent``. This factory follows that shape while
    keeping the model configurable through ``OrchestratorSettings``.
    """

    resolved_settings = settings or OrchestratorSettings.from_env()
    Agent = load_symbol("google.adk.agents.llm_agent", "Agent")
    phase2_workflows = create_phase2_workflows(resolved_settings)
    return Agent(
        model=resolved_settings.model,
        name="root_orchestrator_agent",
        description="Phase-2 root agent for ADK-only workflow orchestration.",
        instruction=ROOT_AGENT_INSTRUCTION,
        tools=[capture_objective, get_orchestrator_status],
        sub_agents=list(phase2_workflows.values()),
    )
