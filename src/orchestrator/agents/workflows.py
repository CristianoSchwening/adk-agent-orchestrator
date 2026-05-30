"""ADK workflow factories for phase 2.

The factories in this module intentionally compose only official ADK Python
agent primitives: ``LlmAgent``, ``SequentialAgent``, ``ParallelAgent`` and
``LoopAgent``. They do not introduce a custom scheduler, task board or runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.config import OrchestratorSettings
from orchestrator.policies import BudgetPolicy
from orchestrator.tools import (
    describe_model_request,
    extract_document_outline,
    fetch_http_text,
    inspect_json_records,
    read_text_file,
    request_human_approval,
)

PHASE_2_WORKFLOW_NAMES = (
    "sequential",
    "parallel",
    "review_critic",
    "iterative_refinement",
    "human_in_the_loop",
)


def _load_adk_agent_primitives() -> tuple[type[Any], type[Any], type[Any], type[Any]]:
    """Load ADK agent primitives without importing custom orchestration code."""

    LlmAgent = load_symbol("google.adk.agents.llm_agent", "Agent")
    SequentialAgent = load_symbol("google.adk.agents.sequential_agent", "SequentialAgent")
    ParallelAgent = load_symbol("google.adk.agents.parallel_agent", "ParallelAgent")
    LoopAgent = load_symbol("google.adk.agents.loop_agent", "LoopAgent")
    return LlmAgent, SequentialAgent, ParallelAgent, LoopAgent


def _llm_agent_factory(settings: OrchestratorSettings) -> Callable[..., Any]:
    """Return a small factory bound to the configured model id."""

    LlmAgent, _, _, _ = _load_adk_agent_primitives()

    def create_llm_agent(
        *,
        name: str,
        description: str,
        instruction: str,
        tools: Iterable[Callable[..., Any]] = (),
        output_key: str | None = None,
        parallel_worker: bool | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": settings.model,
            "name": name,
            "description": description,
            "instruction": instruction.strip(),
            "tools": list(tools),
        }
        if output_key:
            kwargs["output_key"] = output_key
        if parallel_worker is not None:
            kwargs["parallel_worker"] = parallel_worker
        return LlmAgent(**kwargs)

    return create_llm_agent


def create_sequential_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create the Planner → Executor → Critic → Summarizer ADK workflow."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    _, SequentialAgent, _, _ = _load_adk_agent_primitives()
    llm = _llm_agent_factory(resolved_settings)

    return SequentialAgent(
        name="sequential_workflow",
        description=(
            "ADK SequentialAgent for deterministic planning, execution, critique and summary."
        ),
        sub_agents=[
            llm(
                name="sequential_planner_agent",
                description="Breaks the user objective into ordered implementation steps.",
                instruction="""
                Planeje a solução do objetivo recebido em etapas claras, pequenas e verificáveis.
                Escreva premissas, dependências e critérios de sucesso antes de propor execução.
                """,
                tools=[read_text_file, extract_document_outline],
                output_key="sequential_plan",
            ),
            llm(
                name="sequential_executor_agent",
                description="Executes the planned steps at the reasoning level.",
                instruction="""
                Use o plano disponível no estado da sessão para produzir a solução solicitada.
                Preserve rastreabilidade entre etapas do plano e decisões tomadas.
                """,
                tools=[read_text_file, fetch_http_text, inspect_json_records],
                output_key="sequential_execution",
            ),
            llm(
                name="sequential_critic_agent",
                description="Reviews the execution for omissions, risks and inconsistencies.",
                instruction="""
                Revise criticamente a execução: identifique falhas, lacunas, riscos e testes
                ausentes. Se estiver adequada, explique por que ela atende aos critérios.
                """,
                output_key="sequential_critique",
            ),
            llm(
                name="sequential_summarizer_agent",
                description="Summarizes the final answer and review outcome.",
                instruction="""
                Consolide plano, execução e crítica em uma resposta final concisa em português,
                destacando resultado, riscos remanescentes e próximos passos recomendados.
                """,
                tools=[describe_model_request],
                output_key="sequential_summary",
            ),
        ],
    )


def create_parallel_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create an ADK ParallelAgent with independent specialist workers."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    _, _, ParallelAgent, _ = _load_adk_agent_primitives()
    llm = _llm_agent_factory(resolved_settings)

    return ParallelAgent(
        name="parallel_workflow",
        description=(
            "ADK ParallelAgent that evaluates an objective through independent specialists."
        ),
        sub_agents=[
            llm(
                name="parallel_architecture_agent",
                description="Assesses architecture and decomposition concerns.",
                instruction=(
                    "Avalie impactos de arquitetura, interfaces e decomposição do objetivo."
                ),
                tools=[read_text_file, extract_document_outline],
                output_key="parallel_architecture_assessment",
                parallel_worker=True,
            ),
            llm(
                name="parallel_quality_agent",
                description="Assesses tests, observability and quality gates.",
                instruction=(
                    "Avalie estratégia de testes, qualidade, observabilidade e critérios de aceite."
                ),
                tools=[inspect_json_records],
                output_key="parallel_quality_assessment",
                parallel_worker=True,
            ),
            llm(
                name="parallel_risk_agent",
                description="Assesses security, compliance and delivery risks.",
                instruction=(
                    "Avalie riscos de segurança, privacidade, compliance, prazo e operação."
                ),
                tools=[fetch_http_text],
                output_key="parallel_risk_assessment",
                parallel_worker=True,
            ),
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
    _, _, _, LoopAgent = _load_adk_agent_primitives()
    llm = _llm_agent_factory(resolved_settings)

    return LoopAgent(
        name="review_critic_workflow",
        description=(
            "ADK LoopAgent that alternates authoring and critique within the iteration budget."
        ),
        max_iterations=policy.max_iterations,
        sub_agents=[
            llm(
                name="review_author_agent",
                description="Produces or updates a candidate answer.",
                instruction=(
                    "Produza uma resposta candidata e incorpore críticas anteriores se existirem."
                ),
                output_key="review_candidate",
            ),
            llm(
                name="review_critic_agent",
                description="Critiques the candidate answer and calls out required changes.",
                instruction=(
                    "Critique a resposta candidata, liste problemas e sinalize se está pronta."
                ),
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
    _, _, _, LoopAgent = _load_adk_agent_primitives()
    llm = _llm_agent_factory(resolved_settings)

    return LoopAgent(
        name="iterative_refinement_workflow",
        description=(
            "ADK LoopAgent that drafts, evaluates and refines until the iteration budget ends."
        ),
        max_iterations=policy.max_iterations,
        sub_agents=[
            llm(
                name="refinement_drafter_agent",
                description="Creates the initial working draft.",
                instruction=(
                    "Crie um rascunho inicial objetivo, testável e alinhado ao pedido do usuário."
                ),
                output_key="refinement_draft",
            ),
            llm(
                name="refinement_evaluator_agent",
                description="Scores the draft against acceptance criteria.",
                instruction=(
                    "Avalie o rascunho contra critérios de aceite e priorize melhorias concretas."
                ),
                tools=[inspect_json_records, extract_document_outline],
                output_key="refinement_evaluation",
            ),
            llm(
                name="refinement_editor_agent",
                description="Applies improvements identified by the evaluator.",
                instruction=(
                    "Refine o rascunho com base na avaliação, reduzindo ambiguidades e riscos."
                ),
                output_key="refinement_result",
            ),
        ],
    )


def create_human_in_the_loop_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create an ADK SequentialAgent that pauses for explicit human approval."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    _, SequentialAgent, _, _ = _load_adk_agent_primitives()
    llm = _llm_agent_factory(resolved_settings)

    return SequentialAgent(
        name="human_in_the_loop_workflow",
        description="ADK workflow that requests human approval before final execution guidance.",
        sub_agents=[
            llm(
                name="human_context_agent",
                description="Frames the decision that requires human input.",
                instruction=(
                    "Explique o contexto, opções disponíveis, impactos e recomendação para "
                    "aprovação humana."
                ),
                output_key="human_review_context",
            ),
            llm(
                name="human_approval_agent",
                description="Requests a structured approval decision from the human operator.",
                instruction="""
                Antes de prosseguir, use a tool request_human_approval para registrar a decisão
                humana necessária. Não trate a etapa como aprovada sem uma decisão explícita.
                """,
                tools=[request_human_approval],
                output_key="human_approval_decision",
            ),
            llm(
                name="human_followup_agent",
                description="Produces next steps that respect the human approval decision.",
                instruction="""
                Gere os próximos passos respeitando a decisão humana registrada. Se não houver
                aprovação, limite-se a recomendações seguras, perguntas e alternativas.
                """,
                output_key="human_followup",
            ),
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
