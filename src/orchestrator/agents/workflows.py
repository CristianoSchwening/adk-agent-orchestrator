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
    create_context_agent,
    create_critic_agent,
    create_evaluator_agent,
    create_executor_agent,
    create_followup_agent,
    create_llm_specialist_factory,
    create_planner_agent,
    create_refiner_agent,
    create_researcher_agent,
    create_summarizer_agent,
)
from orchestrator.config import (
    OrchestratorSettings,
    ProgressiveFinalResponseStrategy,
    ProgressiveFinalSummarizerMode,
)
from orchestrator.contracts import AgentHelpRequest, AgentHelpResponse, AgentVisibleResponse
from orchestrator.policies import BudgetPolicy
from orchestrator.tools import (
    extract_document_outline,
    fetch_http_text,
    inspect_json_records,
    read_text_file,
)

PHASE_2_WORKFLOW_NAMES = (
    "sequential",
    "parallel",
    "review_critic",
    "iterative_refinement",
    "human_in_the_loop",
    "agent_help_request",
    "progressive_multi_agent_response",
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
    """Create Planner/Researcher/Executor in parallel followed by a Summarizer."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    SequentialAgent, ParallelAgent, _ = _load_adk_workflow_primitives()

    parallel_block = ParallelAgent(
        name="parallel_specialists_agent",
        description="Runs planner, researcher and executor specialists in parallel.",
        sub_agents=[
            create_planner_agent(
                resolved_settings,
                name="parallel_planner_agent",
                output_key="parallel_plan",
                parallel_worker=True,
            ),
            create_researcher_agent(
                resolved_settings,
                name="parallel_researcher_agent",
                output_key="parallel_research",
                parallel_worker=True,
            ),
            create_executor_agent(
                resolved_settings,
                name="parallel_executor_agent",
                output_key="parallel_execution",
                parallel_worker=True,
            ),
        ],
    )

    return SequentialAgent(
        name="parallel_workflow",
        description="ADK workflow that runs parallel specialists and summarizes their outputs.",
        sub_agents=[
            parallel_block,
            create_summarizer_agent(
                resolved_settings,
                name="parallel_summarizer_agent",
                output_key="parallel_summary",
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


def _agent_help_contract_template(
    contract_type: type[AgentHelpRequest] | type[AgentHelpResponse],
) -> dict[str, Any]:
    """Return the required keys for the internal agent-help contract."""

    return {
        "contract": contract_type.__name__,
        "required_fields": [
            "request_id",
            "requester_agent",
            "provider_agent",
            "requested_capability",
            "reason",
            "payload",
            "status",
            "response",
            "metadata",
        ],
    }


def create_agent_help_request_workflow(
    settings: OrchestratorSettings | None = None,
    *,
    budget_policy: BudgetPolicy | None = None,
) -> Any:
    """Create a brokered workflow for bounded specialist-to-specialist help.

    The workflow is deliberately separate from the existing phase-2 workflows:
    a task-owner specialist remains accountable for the primary objective, while
    a broker normalizes any point-in-time help request into ``AgentHelpRequest``
    and ``AgentHelpResponse`` contracts before and after the provider specialist
    contributes. This avoids free peer-to-peer conversation between agents.
    """

    resolved_settings = settings or OrchestratorSettings.from_env()
    policy = budget_policy or BudgetPolicy()
    SequentialAgent, _, _ = _load_adk_workflow_primitives()
    llm = create_llm_specialist_factory(resolved_settings)
    request_contract = _agent_help_contract_template(AgentHelpRequest)
    response_contract = _agent_help_contract_template(AgentHelpResponse)

    task_owner = llm(
        name="agent_help_task_owner_agent",
        description="Owns the primary task and identifies narrowly scoped help needs.",
        instruction=f"""
        Você é o agente responsável pela tarefa principal. Resolva o máximo possível dentro
        da sua especialidade e só solicite apoio pontual quando uma capacidade externa for
        claramente necessária. Não converse diretamente com outros agentes.

        Se precisar de ajuda, emita exatamente um contrato AgentHelpRequest com os campos
        obrigatórios {request_contract["required_fields"]}. Defina requester_agent como seu
        próprio nome, escolha um provider_agent específico, descreva requested_capability,
        reason e payload mínimo necessário. Use status="requested" e deixe response como null.
        Se não precisar de ajuda, explique a decisão e marque metadata.help_needed=false.
        """,
        output_key="agent_help_task_owner_draft",
        tools=[read_text_file, fetch_http_text, inspect_json_records],
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    request_broker = llm(
        name="agent_help_request_broker_agent",
        description="Mediates and validates bounded help requests before provider execution.",
        instruction=f"""
        Você é o broker/mediador. Sua função é impedir conversa livre entre agentes.
        Leia a saída do task owner e normalize no contrato {request_contract}.
        Valide request_id, requester_agent, provider_agent, requested_capability, reason,
        payload, status, response e metadata. Rejeite ou reduza pedidos amplos demais.
        Não acrescente diálogo aberto; entregue somente um AgentHelpRequest estruturado.
        Respeite o limite operacional de {policy.max_model_calls} chamadas de modelo como
        metadata.max_model_calls quando aplicável.
        """,
        output_key="agent_help_request",
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    provider = llm(
        name="agent_help_provider_agent",
        description="Provides one bounded specialist answer only for the brokered request.",
        instruction=f"""
        Você é o especialista provedor. Responda somente ao AgentHelpRequest validado pelo
        broker em agent_help_request. Não inicie conversa com o solicitante e não expanda o
        escopo além de requested_capability, reason e payload.

        Produza um AgentHelpResponse com os campos obrigatórios
        {response_contract["required_fields"]}. Preserve request_id, requester_agent,
        provider_agent e requested_capability. Use status="completed" quando responder,
        ou status="failed"/"rejected" com justificativa em response quando não puder ajudar.
        """,
        output_key="agent_help_provider_response",
        tools=[read_text_file, fetch_http_text, extract_document_outline, inspect_json_records],
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    response_broker = llm(
        name="agent_help_response_broker_agent",
        description="Validates provider output and prepares a bounded handoff to the task owner.",
        instruction=f"""
        Você é o broker/mediador de resposta. Valide agent_help_provider_response contra
        {response_contract}. Garanta que a resposta está vinculada ao mesmo request_id e que
        não há conversa livre, tarefas novas ou delegação em cadeia. Entregue somente o
        AgentHelpResponse estruturado e saneado para o agente responsável.
        """,
        output_key="agent_help_response",
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    finalizer = llm(
        name="agent_help_task_finalizer_agent",
        description="Integrates the brokered help response into the primary task result.",
        instruction="""
        Retome a responsabilidade pela tarefa principal. Use agent_help_response apenas como
        apoio pontual, cite como ele influenciou a solução e finalize sem abrir nova conversa
        com o provedor. Se o broker rejeitou a ajuda, prossiga com premissas explícitas.
        """,
        output_key="agent_help_final_result",
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    return SequentialAgent(
        name="agent_help_request_workflow",
        description=(
            "ADK workflow for a task-owner agent to request bounded specialist help through "
            "a broker using AgentHelpRequest and AgentHelpResponse contracts."
        ),
        sub_agents=[task_owner, request_broker, provider, response_broker, finalizer],
    )


def _progressive_final_strategy_instruction(
    strategy: ProgressiveFinalResponseStrategy,
) -> str:
    """Return an instruction snippet for the configured final-response strategy."""

    strategy_instructions = {
        "last_agent_response": (
            "A resposta final canônica deve ser a última contribuição especializada "
            "publicada por progressive_agent_c, sem síntese adicional obrigatória."
        ),
        "summarizer_response": (
            "A resposta final canônica deve ser a saída de response_chain_summarizer_agent."
        ),
        "root_selected_response": (
            "O root deve selecionar explicitamente a melhor resposta final ou decidir se "
            "uma síntese de fechamento é necessária."
        ),
        "all_visible_responses": (
            "Todas as respostas em progressive_agent_responses devem permanecer visíveis; "
            "não reduza a cadeia a uma única mensagem final por padrão."
        ),
    }
    return strategy_instructions[strategy]


def _create_response_chain_summarizer_agent(
    llm: Any,
    *,
    mode: ProgressiveFinalSummarizerMode,
    strategy: ProgressiveFinalResponseStrategy,
) -> Any:
    """Create the optional final agent that closes the progressive response chain."""

    if mode == "enabled":
        mode_instruction = (
            "final_summarizer_enabled=enabled: gere uma síntese final obrigatória que "
            "feche a cadeia, reconciliando progressive_response_a, progressive_response_b, "
            "progressive_response_c e progressive_agent_responses."
        )
    else:
        mode_instruction = (
            "final_summarizer_enabled=auto: aja como o ponto de decisão do root. "
            "Primeiro decida se a cadeia precisa de síntese final. Se precisar, sintetize; "
            "se não precisar, selecione a resposta existente mais adequada e explique a "
            "decisão sem duplicar conteúdo."
        )

    return llm(
        name="response_chain_summarizer_agent",
        description=(
            "Optionally synthesizes or closes the progressive multi-agent response chain."
        ),
        instruction=f"""
        {mode_instruction}

        Estratégia de finalização configurada: {strategy}.
        {_progressive_final_strategy_instruction(strategy)}

        Regras:
        - Preserve autoria, response_id e depends_on_response_ids ao citar contribuições.
        - Não remova progressive_agent_responses; eles continuam sendo as mensagens
          user-visible publicadas no chat.
        - Produza progressive_final_response com a decisão final, a estratégia aplicada
          e, quando houver síntese, uma resposta curta de fechamento.
        """,
        output_key="progressive_final_response",
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def _agent_visible_response_contract_template() -> dict[str, Any]:
    """Return required keys for the progressive user-visible response entity."""

    return {
        "contract": AgentVisibleResponse.__name__,
        "state_key": "progressive_agent_responses",
        "required_fields": [
            "response_id",
            "agent_name",
            "agent_role",
            "content",
            "depends_on_response_ids",
            "visibility",
            "status",
            "publication_order",
            "created_at",
            "metadata",
        ],
    }


def create_progressive_multi_agent_response_workflow(
    settings: OrchestratorSettings | None = None,
    *,
    budget_policy: BudgetPolicy | None = None,
) -> Any:
    """Create a separate workflow for progressive specialist chat responses.

    Unlike ``agent_help_request``, this mode is not brokered point-in-time help
    between agents. It is a user-experience workflow where several specialists
    intentionally publish successive user-visible contributions. Each later
    contribution may cite prior response IDs as dependencies so the UI can show
    authorship, order and causality.
    """

    resolved_settings = settings or OrchestratorSettings.from_env()
    policy = budget_policy or BudgetPolicy()
    SequentialAgent, _, _ = _load_adk_workflow_primitives()
    llm = create_llm_specialist_factory(resolved_settings)
    visible_response_contract = _agent_visible_response_contract_template()
    required_fields = visible_response_contract["required_fields"]
    progressive_config = resolved_settings.progressive_multi_agent_response
    final_summarizer_mode = progressive_config.final_summarizer_enabled
    final_response_strategy = progressive_config.final_response_strategy
    final_strategy_instruction = _progressive_final_strategy_instruction(final_response_strategy)

    agent_a = llm(
        name="progressive_agent_a",
        description="Publishes the first specialist contribution for the user.",
        instruction=f"""
        Você é o Agente A no workflow progressive_multi_agent_response_workflow.
        Publique a primeira contribuição especializada para o usuário em formato
        AgentVisibleResponse com os campos obrigatórios {required_fields}.

        Regras:
        - Use response_id="response-x", agent_name="progressive_agent_a" e um
          agent_role claro para a sua especialidade.
        - Use depends_on_response_ids=[] porque esta é a primeira resposta.
        - Use visibility="user_visible", status="published" e publication_order=1.
        - Inclua metadata.workflow="progressive_multi_agent_response" e
          metadata.state_key="progressive_agent_responses".
        """,
        output_key="progressive_response_a",
        tools=[read_text_file, fetch_http_text, inspect_json_records],
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    agent_b = llm(
        name="progressive_agent_b",
        description="Publishes a second specialist contribution that depends on Agent A.",
        instruction=f"""
        Você é o Agente B. Leia progressive_response_a como contexto anterior e publique
        uma nova contribuição no formato AgentVisibleResponse com os campos obrigatórios
        {required_fields}.

        Regras:
        - Declare explicitamente depends_on_response_ids=["response-x"].
        - Use response_id="response-z", agent_name="progressive_agent_b",
          visibility="user_visible", status="published" e publication_order=2.
        - Complemente, conteste ou aprofunde a resposta X sem ocultar a causalidade.
        - Respeite o limite operacional de {policy.max_model_calls} chamadas de modelo
          como metadata.max_model_calls quando aplicável.
        """,
        output_key="progressive_response_b",
        tools=[read_text_file, extract_document_outline, inspect_json_records],
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    agent_c = llm(
        name="progressive_agent_c",
        description="Publishes a third contribution that can depend on multiple prior answers.",
        instruction=f"""
        Você é o Agente C. Leia progressive_response_a e progressive_response_b como
        contexto anterior e publique uma terceira contribuição no formato
        AgentVisibleResponse com os campos obrigatórios {required_fields}.

        Regras:
        - Declare depends_on_response_ids=["response-x", "response-z"], demonstrando
          que uma resposta pode depender das respostas X e Z anteriores.
        - Use response_id="response-c", agent_name="progressive_agent_c",
          visibility="user_visible", status="published" e publication_order=3.
        - Mostre claramente onde você usa ou reconcilia as contribuições anteriores.
        """,
        output_key="progressive_response_c",
        tools=[fetch_http_text, extract_document_outline, inspect_json_records],
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    publisher = llm(
        name="progressive_response_publisher_agent",
        description="Normalizes progressive specialist responses into session state.",
        instruction=f"""
        Normalize progressive_response_a, progressive_response_b e progressive_response_c
        em uma lista JSON ordenada de AgentVisibleResponse sob a chave de estado
        progressive_agent_responses. Cada item deve conter exatamente os campos
        obrigatórios {required_fields}.

        Preserve autoria, publication_order e causalidade:
        - response-x não depende de respostas anteriores;
        - response-z depende de response-x;
        - response-c depende de response-x e response-z.

        Configuração de finalização:
        - final_summarizer_enabled={final_summarizer_mode};
        - final_response_strategy={final_response_strategy};
        - {final_strategy_instruction}

        Não transforme este modo em AgentHelpRequest/AgentHelpResponse; este workflow é
        independente e voltado a mensagens sucessivas de especialistas no chat.
        """,
        output_key="progressive_agent_responses",
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    sub_agents = [agent_a, agent_b, agent_c, publisher]
    if final_summarizer_mode in {"enabled", "auto"}:
        sub_agents.append(
            _create_response_chain_summarizer_agent(
                llm,
                mode=final_summarizer_mode,
                strategy=final_response_strategy,
            )
        )

    return SequentialAgent(
        name="progressive_multi_agent_response_workflow",
        description=(
            "ADK workflow for successive user-visible specialist responses with authored "
            "message order and dependency causality stored in progressive_agent_responses."
        ),
        sub_agents=sub_agents,
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
        "agent_help_request": create_agent_help_request_workflow(
            resolved_settings,
            budget_policy=budget_policy,
        ),
        "progressive_multi_agent_response": create_progressive_multi_agent_response_workflow(
            resolved_settings,
            budget_policy=budget_policy,
        ),
    }
