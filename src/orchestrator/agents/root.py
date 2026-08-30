"""Root ADK agent definition for phase 3."""

from __future__ import annotations

import json
from typing import Any

from orchestrator.adk_compat import load_agent_class, load_workflow_classes
from orchestrator.agents.context_intelligence import (
    create_context_intelligence_agent,
    create_context_package_normalizer,
)
from orchestrator.agents.task_dispatcher import create_task_dispatcher_node
from orchestrator.agents.task_planner import (
    create_task_plan_normalizer,
    create_task_planner_agent,
)
from orchestrator.agents.workflows import PHASE_2_WORKFLOW_NAMES, create_phase2_workflows
from orchestrator.config import OrchestratorSettings
from orchestrator.model import create_gemini_model
from orchestrator.tools import PHASE_3_LOCAL_TOOLS, capture_objective, get_orchestrator_status

WORKFLOW_ROUTE_SCHEMA = {
    "type": "object",
    "required": ["selected_workflow", "rationale"],
    "additionalProperties": False,
    "properties": {
        "selected_workflow": {
            "type": "string",
            "enum": list(PHASE_2_WORKFLOW_NAMES),
        },
        "rationale": {
            "type": "string",
            "description": "Concise reason why this workflow best matches the objective.",
        },
    },
}

ROOT_AGENT_INSTRUCTION = """
Você é o Root Orchestrator Agent de uma arquitetura greenfield construída com Google ADK.
Nesta Fase 3, sua responsabilidade é rotear objetivos para workflows ADK equivalentes,
capturar objetivos de forma estruturada, explicar capacidades disponíveis e usar tools ADK
locais seguras quando elas ajudarem a responder.

Regras:
- Receba o TaskPlan validado produzido pelo task_planner_agent e use suas dependências,
  estratégias e necessidades de revisão como sinais para definir o fluxo global. No
  incremento atual, o dispatcher registra essa decisão e executa as tarefas uma por vez.
- Não refaça a decomposição e não altere o TaskPlan durante o roteamento.
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
- Retorne somente o objeto estruturado exigido pelo output_schema. Em selected_workflow,
  escolha exatamente um destes valores:
  sequential, parallel, review_critic, iterative_refinement, human_in_the_loop,
  agent_help_request ou progressive_multi_agent_response.
- Em rationale, registre uma justificativa curta para a escolha. Não liste alternativas.
""".strip()


def _route_payload(node_input: Any) -> dict[str, Any]:
    """Decode the router's structured output without fuzzy text matching."""

    if isinstance(node_input, dict):
        payload = node_input
    elif hasattr(node_input, "model_dump"):
        payload = node_input.model_dump()
    else:
        parts = getattr(node_input, "parts", None) or []
        text = "".join(str(getattr(part, "text", "") or "") for part in parts)
        candidate = (text or str(node_input)).strip()
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("workflow router returned invalid structured output") from exc

    if not isinstance(payload, dict):
        raise ValueError("workflow router output must be a JSON object")
    selected_workflow = payload.get("selected_workflow")
    if selected_workflow not in PHASE_2_WORKFLOW_NAMES:
        supported = ", ".join(PHASE_2_WORKFLOW_NAMES)
        raise ValueError(
            f"workflow router selected unsupported workflow {selected_workflow!r}; "
            f"expected one of: {supported}"
        )
    rationale = payload.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("workflow router rationale must be a non-empty string")
    return {
        "selected_workflow": selected_workflow,
        "rationale": rationale.strip(),
    }


def create_root_agent(settings: OrchestratorSettings | None = None) -> Any:
    """Create the graph-based ADK root workflow and its LLM router node."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    Agent = load_agent_class()
    Workflow, FunctionNode, _, Edge, START = load_workflow_classes()
    phase2_workflows = create_phase2_workflows(resolved_settings)
    kwargs: dict[str, Any] = {
        "model": create_gemini_model(resolved_settings, role="router"),
        "name": "workflow_router_agent",
        "description": "Selects one graph workflow for the current objective.",
        "instruction": ROOT_AGENT_INSTRUCTION,
        "tools": [capture_objective, get_orchestrator_status, *PHASE_3_LOCAL_TOOLS],
        "output_schema": WORKFLOW_ROUTE_SCHEMA,
    }
    router = Agent(**kwargs)
    task_planner = create_task_planner_agent(resolved_settings)
    context_intelligence = create_context_intelligence_agent(resolved_settings)
    context_normalizer = create_context_package_normalizer()
    task_plan_normalizer = create_task_plan_normalizer()
    task_dispatcher = create_task_dispatcher_node(resolved_settings)

    def normalize_route(ctx: Any, node_input: Any) -> str:
        payload = _route_payload(node_input)
        selected_route = payload["selected_workflow"]
        ctx.state["selected_workflow"] = selected_route
        ctx.state["workflow"] = selected_route
        ctx.state["workflow_selection_source"] = "model"
        ctx.state["decision_rationale"] = payload["rationale"]
        ctx.state["workflow_alternatives"] = [
            route for route in phase2_workflows if route != selected_route
        ]
        return selected_route

    route_node = FunctionNode(func=normalize_route, name="normalize_workflow_route")
    edges = [
        Edge(from_node=START, to_node=context_intelligence),
        Edge(from_node=context_intelligence, to_node=context_normalizer),
        Edge(from_node=context_normalizer, to_node=task_planner),
        Edge(from_node=task_planner, to_node=task_plan_normalizer),
        Edge(from_node=task_plan_normalizer, to_node=router),
        Edge(from_node=router, to_node=route_node),
    ]
    edges.append(Edge(from_node=route_node, to_node=task_dispatcher))
    return Workflow(
        name="root_orchestrator_agent",
        description="ADK planning, flow selection and sequential task dispatch.",
        edges=edges,
    )


def create_planned_workflow(
    settings: OrchestratorSettings,
    *,
    workflow_name: str,
) -> Any:
    """Wrap an explicitly selected workflow with the ADK task-planning stage."""

    Workflow, _, _, Edge, START = load_workflow_classes()
    workflows = create_phase2_workflows(settings)
    if workflow_name not in workflows:
        raise ValueError(f"unsupported workflow: {workflow_name}")
    planner = create_task_planner_agent(settings)
    context_intelligence = create_context_intelligence_agent(settings)
    context_normalizer = create_context_package_normalizer()
    normalizer = create_task_plan_normalizer()
    target = create_task_dispatcher_node(settings)

    def select_explicit_workflow(ctx: Any, node_input: Any) -> Any:
        ctx.state["selected_workflow"] = workflow_name
        ctx.state["workflow"] = workflow_name
        ctx.state["workflow_selection_source"] = "explicit"
        return node_input

    selector = load_workflow_classes()[1](
        func=select_explicit_workflow,
        name="select_explicit_workflow",
    )
    return Workflow(
        name=f"planned_{workflow_name}_workflow",
        description="ADK task planning followed by the explicitly selected workflow.",
        edges=[
            Edge(from_node=START, to_node=context_intelligence),
            Edge(from_node=context_intelligence, to_node=context_normalizer),
            Edge(from_node=context_normalizer, to_node=planner),
            Edge(from_node=planner, to_node=normalizer),
            Edge(from_node=normalizer, to_node=selector),
            Edge(from_node=selector, to_node=target),
        ],
    )
