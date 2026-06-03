"""Specialist ADK agent factories.

This module keeps specialist roles separate from workflow composition. The
legacy project had clear concepts for agents, toolkits, subtasks and execution;
this greenfield ADK implementation preserves that separation by defining agent
roles here and composing them in ``workflows.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.config import OrchestratorSettings
from orchestrator.tools import (
    describe_model_request,
    extract_document_outline,
    fetch_http_text,
    inspect_json_records,
    read_text_file,
    request_human_approval,
)


def create_llm_specialist_factory(settings: OrchestratorSettings) -> Callable[..., Any]:
    """Return a small ADK LlmAgent factory bound to the configured model id."""

    LlmAgent = load_symbol("google.adk.agents.llm_agent", "Agent")

    def create_llm_agent(
        *,
        name: str,
        description: str,
        instruction: str,
        tools: Iterable[Callable[..., Any]] = (),
        output_key: str | None = None,
        parallel_worker: bool | None = None,
        disallow_transfer_to_parent: bool | None = None,
        disallow_transfer_to_peers: bool | None = None,
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
        if disallow_transfer_to_parent is not None:
            kwargs["disallow_transfer_to_parent"] = disallow_transfer_to_parent
        if disallow_transfer_to_peers is not None:
            kwargs["disallow_transfer_to_peers"] = disallow_transfer_to_peers
        return LlmAgent(**kwargs)

    return create_llm_agent


def create_planner_agent(
    settings: OrchestratorSettings,
    *,
    name: str = "planner_agent",
    output_key: str = "plan",
    parallel_worker: bool | None = None,
) -> Any:
    """Create a planning specialist that decomposes objectives into steps."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name=name,
        description="Breaks the user objective into ordered implementation steps.",
        instruction="""
        Planeje a solução do objetivo recebido em etapas claras, pequenas e verificáveis.
        Escreva premissas, dependências e critérios de sucesso antes de propor execução.
        """,
        tools=[read_text_file, extract_document_outline],
        output_key=output_key,
        parallel_worker=parallel_worker,
    )


def create_executor_agent(
    settings: OrchestratorSettings,
    *,
    name: str = "executor_agent",
    output_key: str = "execution_result",
    parallel_worker: bool | None = None,
) -> Any:
    """Create an execution specialist that produces an implementation result."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name=name,
        description="Executes the planned steps at the reasoning level.",
        instruction="""
        Use o plano disponível no estado da sessão para produzir a solução solicitada.
        Preserve rastreabilidade entre etapas do plano e decisões tomadas.
        """,
        tools=[read_text_file, fetch_http_text, inspect_json_records],
        output_key=output_key,
        parallel_worker=parallel_worker,
    )


def create_critic_agent(
    settings: OrchestratorSettings,
    *,
    name: str = "critic_agent",
    output_key: str = "critic_result",
    parallel_worker: bool | None = None,
) -> Any:
    """Create a critic specialist for review and risk detection."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name=name,
        description="Reviews outputs for omissions, risks and inconsistencies.",
        instruction="""
        Revise criticamente a resposta candidata: identifique falhas, lacunas, riscos e testes
        ausentes. Se estiver adequada, explique por que ela atende aos critérios.
        """,
        output_key=output_key,
        parallel_worker=parallel_worker,
    )


def create_summarizer_agent(
    settings: OrchestratorSettings,
    *,
    name: str = "summarizer_agent",
    output_key: str = "final_summary",
    parallel_worker: bool | None = None,
) -> Any:
    """Create a summarization specialist for final responses."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name=name,
        description="Summarizes the final answer and review outcome.",
        instruction="""
        Consolide plano, execução e crítica em uma resposta final concisa em português,
        destacando resultado, riscos remanescentes e próximos passos recomendados.
        """,
        tools=[describe_model_request],
        output_key=output_key,
        parallel_worker=parallel_worker,
    )


def create_researcher_agent(
    settings: OrchestratorSettings,
    *,
    name: str = "researcher_agent",
    output_key: str = "research_result",
    parallel_worker: bool | None = None,
) -> Any:
    """Create a research specialist for independent evidence gathering."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name=name,
        description="Researches supporting context, references and constraints.",
        instruction="""
        Pesquise contexto, restrições, riscos e evidências úteis para o objetivo.
        Priorize fatos verificáveis e destaque incertezas.
        """,
        tools=[read_text_file, fetch_http_text, extract_document_outline],
        output_key=output_key,
        parallel_worker=parallel_worker,
    )


def create_refiner_agent(
    settings: OrchestratorSettings,
    *,
    name: str = "refiner_agent",
    output_key: str = "refinement_result",
    parallel_worker: bool | None = None,
) -> Any:
    """Create a refiner specialist that applies critique-driven improvements."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name=name,
        description="Applies improvements identified by an evaluator or critic.",
        instruction="""
        Refine o rascunho com base na avaliação, reduzindo ambiguidades, riscos e lacunas.
        Preserve as decisões corretas e explique mudanças relevantes.
        """,
        output_key=output_key,
        parallel_worker=parallel_worker,
    )


def create_approval_agent(
    settings: OrchestratorSettings,
    *,
    name: str = "approval_agent",
    output_key: str = "approval_decision",
    parallel_worker: bool | None = None,
) -> Any:
    """Create a human-approval specialist for HITL workflows."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name=name,
        description="Requests a structured approval decision from the human operator.",
        instruction="""
        Antes de prosseguir, use a tool request_human_approval para registrar a decisão
        humana necessária. Não trate a etapa como aprovada sem uma decisão explícita.
        """,
        tools=[request_human_approval],
        output_key=output_key,
        parallel_worker=parallel_worker,
    )


def create_architecture_agent(settings: OrchestratorSettings) -> Any:
    """Create the parallel architecture assessment specialist."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name="parallel_architecture_agent",
        description="Assesses architecture and decomposition concerns.",
        instruction="Avalie impactos de arquitetura, interfaces e decomposição do objetivo.",
        tools=[read_text_file, extract_document_outline],
        output_key="parallel_architecture_assessment",
        parallel_worker=True,
    )


def create_quality_agent(settings: OrchestratorSettings) -> Any:
    """Create the parallel quality assessment specialist."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name="parallel_quality_agent",
        description="Assesses tests, observability and quality gates.",
        instruction=(
            "Avalie estratégia de testes, qualidade, observabilidade e critérios de aceite."
        ),
        tools=[inspect_json_records],
        output_key="parallel_quality_assessment",
        parallel_worker=True,
    )


def create_risk_agent(settings: OrchestratorSettings) -> Any:
    """Create the parallel risk assessment specialist."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name="parallel_risk_agent",
        description="Assesses security, compliance and delivery risks.",
        instruction="Avalie riscos de segurança, privacidade, compliance, prazo e operação.",
        tools=[fetch_http_text],
        output_key="parallel_risk_assessment",
        parallel_worker=True,
    )


def create_context_agent(settings: OrchestratorSettings) -> Any:
    """Create the HITL context-framing specialist."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name="human_context_agent",
        description="Frames the decision that requires human input.",
        instruction=(
            "Explique o contexto, opções disponíveis, impactos e recomendação para "
            "aprovação humana."
        ),
        output_key="human_review_context",
    )


def create_followup_agent(settings: OrchestratorSettings) -> Any:
    """Create the HITL follow-up specialist."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name="human_followup_agent",
        description="Produces next steps that respect the human approval decision.",
        instruction="""
        Gere os próximos passos respeitando a decisão humana registrada. Se não houver
        aprovação, limite-se a recomendações seguras, perguntas e alternativas.
        """,
        output_key="human_followup",
    )


def create_evaluator_agent(settings: OrchestratorSettings) -> Any:
    """Create the refinement evaluator specialist."""

    llm = create_llm_specialist_factory(settings)
    return llm(
        name="refinement_evaluator_agent",
        description="Scores the draft against acceptance criteria.",
        instruction="Avalie o rascunho contra critérios de aceite e priorize melhorias concretas.",
        tools=[inspect_json_records, extract_document_outline],
        output_key="refinement_evaluation",
    )
