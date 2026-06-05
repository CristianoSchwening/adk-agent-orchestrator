"""Root ADK agent definition for phase 3."""

from __future__ import annotations

from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.agents.workflows import create_phase2_workflows
from orchestrator.config import OrchestratorSettings
from orchestrator.tools import PHASE_3_LOCAL_TOOLS, capture_objective, get_orchestrator_status

ROOT_AGENT_INSTRUCTION = """
Você é o Root Orchestrator Agent de uma arquitetura greenfield construída com Google ADK.
Nesta Fase 3, sua responsabilidade é rotear objetivos para workflows ADK equivalentes,
capturar objetivos de forma estruturada, explicar capacidades disponíveis e usar tools ADK
locais seguras quando elas ajudarem a responder.

Regras:
- Use a tool capture_objective quando o usuário informar um objetivo.
- Use a tool get_orchestrator_status quando precisar explicar capacidades atuais.
- Use list_available_tools antes de prometer uma capacidade de ferramenta.
- Use tools locais apenas para operações seguras, com escopo limitado, timeout e erros padronizados.
- Quando adequado, delegue para os subagentes/workflows ADK disponíveis: sequential,
  parallel, review_critic, iterative_refinement, human_in_the_loop, agent_help_request e
  progressive_multi_agent_response.
- Escolha agent_help_request quando a tarefa principal pertence claramente a um agente
  responsável, mas ele pode precisar de apoio pontual de outro especialista; nesse modo,
  a ajuda deve passar por broker/mediador e pelos contratos AgentHelpRequest e
  AgentHelpResponse, sem conversa livre entre agentes.
- Escolha progressive_multi_agent_response quando a melhor experiência do usuário for
  mostrar no chat contribuições sucessivas de especialistas, com autoria, ordem de
  publicação e dependências causais entre respostas. Não trate esse modo como variação
  interna de agent_help_request: ele não usa broker de ajuda; ele publica mensagens
  progressivas em progressive_agent_responses.
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
        description="Phase-3 root agent for ADK-only workflow and tool orchestration.",
        instruction=ROOT_AGENT_INSTRUCTION,
        tools=[capture_objective, get_orchestrator_status, *PHASE_3_LOCAL_TOOLS],
        sub_agents=list(phase2_workflows.values()),
    )
