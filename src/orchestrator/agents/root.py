"""Root ADK agent definition for phase 3."""

from __future__ import annotations

from typing import Any

from orchestrator.adk_compat import load_agent_class, load_workflow_classes
from orchestrator.agents.workflows import create_phase2_workflows
from orchestrator.config import OrchestratorSettings
from orchestrator.model import create_gemini_model
from orchestrator.tools import PHASE_3_LOCAL_TOOLS, capture_objective, get_orchestrator_status
from orchestrator.workspace import AGENT_STEP_RESPONSE_SCHEMA, with_workspace_instruction

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
- Se o workspace operacional estiver habilitado, coloque exatamente um destes tokens no
  campo result. Caso contrário, responda somente com o token, sem pontuação adicional:
  sequential, parallel, review_critic, iterative_refinement, human_in_the_loop,
  agent_help_request ou progressive_multi_agent_response.
""".strip()


def create_root_agent(settings: OrchestratorSettings | None = None) -> Any:
    """Create the graph-based ADK root workflow and its LLM router node."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    Agent = load_agent_class()
    Workflow, FunctionNode, _, Edge, START = load_workflow_classes()
    phase2_workflows = create_phase2_workflows(resolved_settings)
    kwargs: dict[str, Any] = {
        "model": create_gemini_model(resolved_settings),
        "name": "workflow_router_agent",
        "description": "Selects one graph workflow for the current objective.",
        "instruction": (
            with_workspace_instruction(ROOT_AGENT_INSTRUCTION)
            if resolved_settings.workspace_enabled
            else ROOT_AGENT_INSTRUCTION
        ),
        "tools": [capture_objective, get_orchestrator_status, *PHASE_3_LOCAL_TOOLS],
    }
    if resolved_settings.workspace_enabled:
        kwargs["output_schema"] = AGENT_STEP_RESPONSE_SCHEMA
    router = Agent(**kwargs)

    def normalize_route(ctx: Any, node_input: Any) -> str:
        parts = getattr(node_input, "parts", None) or []
        text = "".join(str(getattr(part, "text", "") or "") for part in parts)
        candidate = (text or str(node_input)).strip().lower()
        selected_route = "sequential"
        for route in phase2_workflows:
            if route in candidate:
                selected_route = route
                break
        ctx.state["selected_workflow"] = selected_route
        ctx.state["workflow"] = selected_route
        ctx.state["workflow_alternatives"] = [
            route for route in phase2_workflows if route != selected_route
        ]
        return selected_route

    route_node = FunctionNode(func=normalize_route, name="normalize_workflow_route")
    edges = [Edge(from_node=START, to_node=router), Edge(from_node=router, to_node=route_node)]
    edges.extend(
        Edge(from_node=route_node, to_node=workflow, route=route)
        for route, workflow in phase2_workflows.items()
    )
    return Workflow(
        name="root_orchestrator_agent",
        description="Graph-based root orchestrator with one routed workflow per objective.",
        edges=edges,
    )
