"""ADK agents for guarded, bounded replanning."""

from __future__ import annotations

from typing import Any

from orchestrator.adk_compat import load_agent_class
from orchestrator.agents.task_planner import TASK_PLAN_DRAFT_SCHEMA
from orchestrator.config import OrchestratorSettings
from orchestrator.model import create_gemini_model

REPLAN_GUARD_SCHEMA = {
    "type": "object",
    "required": ["trigger", "rationale"],
    "additionalProperties": False,
    "properties": {
        "trigger": {
            "type": "string",
            "enum": [
                "none",
                "blocker_detected",
                "assumption_invalidated",
                "objective_changed",
                "acceptance_criteria_failed",
            ],
        },
        "rationale": {"type": "string"},
    },
}


def create_replan_guard_agent(settings: OrchestratorSettings) -> Any:
    Agent = load_agent_class()
    return Agent(
        model=create_gemini_model(settings, role="reasoning"),
        name="replan_guard_agent",
        description="Allows replanning only for explicitly authorized conditions.",
        instruction="""
        Avalie o resultado da tarefa contra seus critérios, premissas, bloqueios e objetivo.
        Retorne none quando a execução pode continuar. Autorize somente um destes gatilhos:
        blocker_detected, assumption_invalidated, objective_changed ou
        acceptance_criteria_failed. Não autorize por preferência estilística ou mera melhoria.
        Retorne somente o objeto estruturado exigido.
        """,
        output_schema=REPLAN_GUARD_SCHEMA,
        output_key="replan_guard_decision",
    )


def create_replanner_agent(settings: OrchestratorSettings) -> Any:
    Agent = load_agent_class()
    return Agent(
        model=create_gemini_model(settings, role="reasoning"),
        name="controlled_replanner_agent",
        description="Creates a new TaskPlan draft after an authorized trigger.",
        instruction="""
        Crie uma revisão completa do TaskPlan usando o plano anterior, histórico de execução,
        ContextPackage e ReplanRequest recebidos. Preserve tarefas concluídas quando ainda
        válidas, corrija a causa do gatilho e mantenha IDs de tarefa estáveis quando o trabalho
        não mudou. Não execute tarefas. Retorne somente o schema de TaskPlan draft exigido.
        """,
        output_schema=TASK_PLAN_DRAFT_SCHEMA,
        output_key="replanned_task_plan_draft",
    )
