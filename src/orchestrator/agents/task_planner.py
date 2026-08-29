"""ADK-native LLM task planner and deterministic plan materialization."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from orchestrator.adk_compat import load_agent_class, load_workflow_classes
from orchestrator.config import OrchestratorSettings
from orchestrator.model import create_gemini_model
from orchestrator.planning import Deliverable, Goal, PlannedTask, TaskPlan, validate_task_plan

TASK_PLAN_DRAFT_SCHEMA = {
    "type": "object",
    "required": ["goal", "tasks", "deliverables", "assumptions"],
    "additionalProperties": False,
    "properties": {
        "goal": {
            "type": "object",
            "required": ["objective", "constraints", "success_criteria"],
            "additionalProperties": False,
            "properties": {
                "objective": {"type": "string"},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "success_criteria": {"type": "array", "items": {"type": "string"}},
            },
        },
        "tasks": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "required": [
                    "task_id",
                    "title",
                    "description",
                    "task_type",
                    "depends_on",
                    "required_capabilities",
                    "acceptance_criteria",
                    "strategy",
                    "requires_review",
                    "requires_approval",
                ],
                "additionalProperties": False,
                "properties": {
                    "task_id": {"type": "string", "pattern": "^TASK-[A-Za-z0-9_.-]+$"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "task_type": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "required_capabilities": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "acceptance_criteria": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    "strategy": {
                        "type": "string",
                        "enum": [
                            "single_agent",
                            "sequential",
                            "parallel",
                            "review_critic",
                            "iterative_refinement",
                            "human_in_the_loop",
                            "verification",
                        ],
                    },
                    "requires_review": {"type": "boolean"},
                    "requires_approval": {"type": "boolean"},
                },
            },
        },
        "deliverables": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["deliverable_id", "description"],
                "additionalProperties": False,
                "properties": {
                    "deliverable_id": {
                        "type": "string",
                        "pattern": "^DEL-[A-Za-z0-9_.-]+$",
                    },
                    "description": {"type": "string"},
                },
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
}

TASK_PLANNER_INSTRUCTION = """
Você é o Task Planner generalista do orquestrador. Converta o objetivo do usuário em um
plano pequeno, executável e independente de domínio.

Regras:
- Preserve o objetivo e as restrições expressas pelo usuário; não invente requisitos.
- Produza entre 1 e 12 tarefas. Prefira poucas tarefas coesas e verificáveis.
- Use IDs TASK-001, TASK-002 etc. e dependências apenas para tarefas do mesmo plano.
- Declare capacidades, não nomes de agentes.
- Defina ao menos um critério de aceite observável para cada tarefa.
- Use parallel apenas quando trabalhos forem realmente independentes.
- Use review_critic ou iterative_refinement somente quando revisão melhorar o entregável.
- Use human_in_the_loop apenas quando uma decisão humana for indispensável.
- Não execute tarefas, não escolha agentes e não escreva o resultado final.
- Retorne somente o objeto exigido pelo output_schema.
""".strip()


def create_task_planner_agent(settings: OrchestratorSettings) -> Any:
    """Create the official ADK LlmAgent that drafts a structured task plan."""

    LlmAgent = load_agent_class()
    return LlmAgent(
        model=create_gemini_model(settings, role="reasoning"),
        name="task_planner_agent",
        description="Decomposes a user goal into a validated, domain-neutral task DAG.",
        instruction=TASK_PLANNER_INSTRUCTION,
        output_schema=TASK_PLAN_DRAFT_SCHEMA,
        output_key="task_plan_draft",
    )


def task_plan_from_draft(value: Any) -> TaskPlan:
    """Decode an ADK structured output and materialize a versioned task plan."""

    payload = _structured_payload(value)
    goal = payload.get("goal") or {}
    plan = TaskPlan(
        plan_id=f"PLAN-{uuid4()}",
        status="validated",
        goal=Goal(
            objective=str(goal.get("objective") or ""),
            constraints=[str(item) for item in goal.get("constraints") or []],
            success_criteria=[str(item) for item in goal.get("success_criteria") or []],
        ),
        tasks=[
            PlannedTask(
                task_id=str(item.get("task_id") or ""),
                title=str(item.get("title") or ""),
                description=str(item.get("description") or ""),
                task_type=str(item.get("task_type") or ""),
                depends_on=[str(entry) for entry in item.get("depends_on") or []],
                required_capabilities=[
                    str(entry) for entry in item.get("required_capabilities") or []
                ],
                acceptance_criteria=[
                    str(entry) for entry in item.get("acceptance_criteria") or []
                ],
                strategy=item.get("strategy", "single_agent"),
                requires_review=bool(item.get("requires_review", False)),
                requires_approval=bool(item.get("requires_approval", False)),
            )
            for item in payload.get("tasks") or []
            if isinstance(item, dict)
        ],
        deliverables=[
            Deliverable(
                deliverable_id=str(item.get("deliverable_id") or ""),
                description=str(item.get("description") or ""),
            )
            for item in payload.get("deliverables") or []
            if isinstance(item, dict)
        ],
        assumptions=[str(item) for item in payload.get("assumptions") or []],
    )
    return validate_task_plan(plan)


def create_task_plan_normalizer() -> Any:
    """Create an ADK FunctionNode that validates and stores the planner output."""

    _, FunctionNode, _, _, _ = load_workflow_classes()

    def normalize(ctx: Any, node_input: Any) -> str:
        plan = task_plan_from_draft(node_input)
        ctx.state["task_plan"] = plan.to_dict()
        ctx.state["task_plan_status"] = "validated"
        ctx.state["task_plan_source"] = "llm"
        return json.dumps(
            {"objective": plan.goal.objective, "task_plan": plan.to_dict()},
            ensure_ascii=False,
        )

    return FunctionNode(func=normalize, name="normalize_task_plan")


def _structured_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        payload = value
    elif hasattr(value, "model_dump"):
        payload = value.model_dump()
    else:
        parts = getattr(value, "parts", None) or []
        text = "".join(str(getattr(part, "text", "") or "") for part in parts)
        try:
            payload = json.loads((text or str(value)).strip())
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("task planner returned invalid structured output") from exc
    if not isinstance(payload, dict):
        raise ValueError("task planner output must be a JSON object")
    return payload
