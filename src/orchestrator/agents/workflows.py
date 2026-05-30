"""ADK workflow factories for phase 2+.

Workflow composition stays separate from specialist agent definitions. The
specialists live in ``orchestrator.agents.specialists`` while this module only
assembles official ADK workflow primitives: ``SequentialAgent``,
``ParallelAgent`` and ``LoopAgent``.
"""

from __future__ import annotations

from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.agents.specialists import (
    create_approval_agent,
    create_architecture_agent,
    create_context_agent,
    create_critic_agent,
    create_evaluator_agent,
    create_executor_agent,
    create_followup_agent,
    create_planner_agent,
    create_quality_agent,
    create_refiner_agent,
    create_risk_agent,
    create_summarizer_agent,
)
from orchestrator.config import OrchestratorSettings
from orchestrator.policies import BudgetPolicy

PHASE_2_WORKFLOW_NAMES = (
    "sequential",
    "parallel",
    "review_critic",
    "iterative_refinement",
    "human_in_the_loop",
)


def _load_adk_workflow_primitives() -> tuple[type[Any], type[Any], type[Any]]:
    """Load ADK workflow primitives without importing custom orchestration code."""

    SequentialAgent = load_symbol("google.adk.agents.sequential_agent", "SequentialAgent")
    ParallelAgent = load_symbol("google.adk.agents.parallel_agent", "ParallelAgent")
    LoopAgent = load_symbol("google.adk.agents.loop_agent", "LoopAgent")
    return SequentialAgent, ParallelAgent, LoopAgent


def create_sequential_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create the Planner → Executor → Critic → Summarizer ADK workflow."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    SequentialAgent, _, _ = _load_adk_workflow_primitives()

    return SequentialAgent(
        name="sequential_workflow",
        description=(
            "ADK SequentialAgent for deterministic planning, execution, critique and summary."
        ),
        sub_agents=[
            create_planner_agent(
                resolved_settings,
                name="sequential_planner_agent",
                output_key="sequential_plan",
            ),
            create_executor_agent(
                resolved_settings,
                name="sequential_executor_agent",
                output_key="sequential_execution",
            ),
            create_critic_agent(
                resolved_settings,
                name="sequential_critic_agent",
                output_key="sequential_critique",
            ),
            create_summarizer_agent(
                resolved_settings,
                name="sequential_summarizer_agent",
                output_key="sequential_summary",
            ),
        ],
    )


def create_parallel_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create an ADK ParallelAgent with independent specialist workers."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    _, ParallelAgent, _ = _load_adk_workflow_primitives()

    return ParallelAgent(
        name="parallel_workflow",
        description=(
            "ADK ParallelAgent that evaluates an objective through independent specialists."
        ),
        sub_agents=[
            create_architecture_agent(resolved_settings),
            create_quality_agent(resolved_settings),
            create_risk_agent(resolved_settings),
        ],
    )


def create_review_critic_workflow(
    settings: OrchestratorSettings | None = None,
    *,
    budget_policy: BudgetPolicy | None = None,
) -> Any:
    """Create an ADK LoopAgent for draft/review cycles."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    policy = budget_policy or BudgetPolicy()
    _, _, LoopAgent = _load_adk_workflow_primitives()

    return LoopAgent(
        name="review_critic_workflow",
        description=(
            "ADK LoopAgent that alternates authoring and critique within the iteration budget."
        ),
        max_iterations=policy.max_iterations,
        sub_agents=[
            create_executor_agent(
                resolved_settings,
                name="review_author_agent",
                output_key="review_candidate",
            ),
            create_critic_agent(
                resolved_settings,
                name="review_critic_agent",
                output_key="review_critique",
            ),
        ],
    )


def create_iterative_refinement_workflow(
    settings: OrchestratorSettings | None = None,
    *,
    budget_policy: BudgetPolicy | None = None,
) -> Any:
    """Create an ADK LoopAgent for iterative refinement."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    policy = budget_policy or BudgetPolicy()
    _, _, LoopAgent = _load_adk_workflow_primitives()

    return LoopAgent(
        name="iterative_refinement_workflow",
        description=(
            "ADK LoopAgent that drafts, evaluates and refines until the iteration budget ends."
        ),
        max_iterations=policy.max_iterations,
        sub_agents=[
            create_planner_agent(
                resolved_settings,
                name="refinement_drafter_agent",
                output_key="refinement_draft",
            ),
            create_evaluator_agent(resolved_settings),
            create_refiner_agent(
                resolved_settings,
                name="refinement_editor_agent",
                output_key="refinement_result",
            ),
        ],
    )


def create_human_in_the_loop_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create an ADK SequentialAgent that pauses for explicit human approval."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    SequentialAgent, _, _ = _load_adk_workflow_primitives()

    return SequentialAgent(
        name="human_in_the_loop_workflow",
        description="ADK workflow that requests human approval before final execution guidance.",
        sub_agents=[
            create_context_agent(resolved_settings),
            create_approval_agent(
                resolved_settings,
                name="human_approval_agent",
                output_key="human_approval_decision",
            ),
            create_followup_agent(resolved_settings),
        ],
    )


def create_phase2_workflows(
    settings: OrchestratorSettings | None = None,
    *,
    budget_policy: BudgetPolicy | None = None,
) -> dict[str, Any]:
    """Create all phase-2 workflow agents keyed by their public workflow name."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    return {
        "sequential": create_sequential_workflow(resolved_settings),
        "parallel": create_parallel_workflow(resolved_settings),
        "review_critic": create_review_critic_workflow(
            resolved_settings,
            budget_policy=budget_policy,
        ),
        "iterative_refinement": create_iterative_refinement_workflow(
            resolved_settings,
            budget_policy=budget_policy,
        ),
        "human_in_the_loop": create_human_in_the_loop_workflow(resolved_settings),
    }
