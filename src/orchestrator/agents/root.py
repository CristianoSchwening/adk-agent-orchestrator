"""Root ADK agent definition for phase 1."""

from __future__ import annotations

from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.config import OrchestratorSettings
from orchestrator.tools import capture_objective, get_orchestrator_status

ROOT_AGENT_INSTRUCTION = """
Você é o Root Orchestrator Agent de uma arquitetura greenfield construída com Google ADK.
Nesta Fase 1, sua responsabilidade é validar a fundação: receber objetivos, capturar o
objetivo de forma estruturada, explicar que os workflows multiagente serão adicionados nas
próximas fases e retornar uma resposta objetiva em português.

Regras:
- Use a tool capture_objective quando o usuário informar um objetivo.
- Use a tool get_orchestrator_status quando precisar explicar capacidades atuais.
- Não prometa execução real de subtarefas ainda; esta fase entrega apenas bootstrap ADK.
""".strip()


def create_root_agent(settings: OrchestratorSettings | None = None) -> Any:
    """Create the official ADK root agent.

    ADK's Python quickstart defines a required ``root_agent`` using
    ``google.adk.agents.llm_agent.Agent``. This factory follows that shape while
    keeping the model configurable through ``OrchestratorSettings``.
    """

    resolved_settings = settings or OrchestratorSettings.from_env()
    Agent = load_symbol("google.adk.agents.llm_agent", "Agent")
    return Agent(
        model=resolved_settings.model,
        name="root_orchestrator_agent",
        description="Phase-1 root agent for the ADK-only orchestrator foundation.",
        instruction=ROOT_AGENT_INSTRUCTION,
        tools=[capture_objective, get_orchestrator_status],
    )
