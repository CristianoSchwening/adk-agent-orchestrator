"""ADK workflow factories for phase 2+.

Workflow composition stays separate from specialist agent definitions. The
specialists live in ``orchestrator.agents.specialists`` while this module only
assembles graph workflows with the public ``google.adk.workflow`` API.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from orchestrator.adk_compat import load_workflow_classes
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
from orchestrator.loops.rubric import STANDARD_QUALITY_RUBRIC
from orchestrator.loops.stop_condition import make_quality_stop_callback
from orchestrator.loops.verification import VerificationLoop
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


def _workflow(name: str, description: str, *nodes: Any) -> Any:
    """Build a deterministic chain with ADK's graph Workflow primitive."""

    Workflow, _, _, _, _ = load_workflow_classes()
    return Workflow(name=name, description=description, edges=[("START", *nodes)])


def create_sequential_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create the Planner → Executor → Critic → Summarizer ADK workflow."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    return _workflow(
        "sequential_workflow",
        "ADK graph for deterministic planning, execution, critique and summary.",
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
    )


def create_parallel_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create Planner/Researcher/Executor in parallel followed by a Summarizer."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    Workflow, _, JoinNode, _, _ = load_workflow_classes()
    planner = create_planner_agent(
        resolved_settings, name="parallel_planner_agent", output_key="parallel_plan"
    )
    researcher = create_researcher_agent(
        resolved_settings, name="parallel_researcher_agent", output_key="parallel_research"
    )
    executor = create_executor_agent(
        resolved_settings, name="parallel_executor_agent", output_key="parallel_execution"
    )
    join = JoinNode(name="parallel_specialists_join")
    summarizer = create_summarizer_agent(
        resolved_settings, name="parallel_summarizer_agent", output_key="parallel_summary"
    )
    return Workflow(
        name="parallel_workflow",
        description="ADK graph that runs parallel specialists and summarizes their outputs.",
        edges=[("START", (planner, researcher, executor), join, summarizer)],
    )


def _loop_gate(name: str, stop_callback: Any, final_state_key: str) -> Any:
    """Create a routed graph node that applies quality and budget termination."""

    _, FunctionNode, _, _, _ = load_workflow_classes()

    def decide(ctx: Any) -> str:
        state = ctx.state
        snapshot = state.to_dict() if hasattr(state, "to_dict") else dict(state)
        snapshot["loop_iteration"] = state.get(f"{name}_iteration", 0)
        should_stop = stop_callback(snapshot)
        if snapshot.get("loop_iterations_used", 0) >= stop_callback.budget_policy.max_iterations:
            should_stop = True
            snapshot["loop_stop_reason"] = "budget_exhausted"
        state.update(
            {
                key: value
                for key, value in snapshot.items()
                if key.startswith("loop_") or key == "grader_result"
            }
        )
        state[f"{name}_iteration"] = snapshot["loop_iteration"]
        if should_stop:
            state[f"{name}_final_output"] = state.get(final_state_key, "")
            return "done"
        return "continue"

    return FunctionNode(func=decide, name=name)


def _loop_initializer(name: str) -> Any:
    """Reset per-invocation graph loop counters before entering a cycle."""

    _, FunctionNode, _, _, _ = load_workflow_classes()

    def initialize(ctx: Any, node_input: Any) -> Any:
        ctx.state[f"{name}_iteration"] = 0
        return node_input

    return FunctionNode(func=initialize, name=f"{name}_initializer")


def _final_output_node(name: str, state_key: str) -> Any:
    """Create a terminal node that emits the selected state value."""

    _, FunctionNode, _, _, _ = load_workflow_classes()

    def final_output(ctx: Any) -> Any:
        return ctx.state.get(state_key, "")

    return FunctionNode(func=final_output, name=name)


def create_review_critic_workflow(
    settings: OrchestratorSettings | None = None,
    *,
    budget_policy: BudgetPolicy | None = None,
) -> Any:
    """Create a conditional ADK graph for bounded draft/review cycles."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    policy = budget_policy or BudgetPolicy()
    Workflow, _, _, Edge, START = load_workflow_classes()

    v_loop = VerificationLoop(
        rubric=STANDARD_QUALITY_RUBRIC,
        max_iterations=policy.max_iterations,
        threshold=policy.quality_threshold,
    )
    stop_callback = make_quality_stop_callback(
        verification_loop=v_loop,
        budget_policy=policy,
        output_key="review_candidate",
    )

    author = create_executor_agent(
        resolved_settings, name="review_author_agent", output_key="review_candidate"
    )
    critic = create_critic_agent(
        resolved_settings, name="review_critic_agent", output_key="review_critique"
    )
    gate = _loop_gate("review_critic_gate", stop_callback, "review_candidate")
    initializer = _loop_initializer("review_critic_gate")
    finalizer = _final_output_node("review_critic_finalizer", "review_candidate")
    return Workflow(
        name="review_critic_workflow",
        description="ADK graph that alternates authoring and critique within a budget.",
        edges=[
            Edge(from_node=START, to_node=initializer),
            Edge(from_node=initializer, to_node=author),
            Edge(from_node=author, to_node=critic),
            Edge(from_node=critic, to_node=gate),
            Edge(from_node=gate, to_node=author, route="continue"),
            Edge(from_node=gate, to_node=finalizer, route="done"),
        ],
    )


def create_iterative_refinement_workflow(
    settings: OrchestratorSettings | None = None,
    *,
    budget_policy: BudgetPolicy | None = None,
) -> Any:
    """Create a conditional ADK graph for iterative refinement."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    policy = budget_policy or BudgetPolicy()
    Workflow, _, _, Edge, START = load_workflow_classes()
    v_loop = VerificationLoop(
        rubric=STANDARD_QUALITY_RUBRIC,
        max_iterations=policy.max_iterations,
        threshold=policy.quality_threshold,
    )
    stop_callback = make_quality_stop_callback(
        verification_loop=v_loop,
        budget_policy=policy,
        output_key="refinement_result",
    )
    drafter = create_planner_agent(
        resolved_settings, name="refinement_drafter_agent", output_key="refinement_draft"
    )
    evaluator = create_evaluator_agent(resolved_settings)
    editor = create_refiner_agent(
        resolved_settings, name="refinement_editor_agent", output_key="refinement_result"
    )
    gate = _loop_gate("iterative_refinement_gate", stop_callback, "refinement_result")
    initializer = _loop_initializer("iterative_refinement_gate")
    finalizer = _final_output_node("iterative_refinement_finalizer", "refinement_result")
    return Workflow(
        name="iterative_refinement_workflow",
        description="ADK graph that drafts, evaluates and refines within a budget.",
        edges=[
            Edge(from_node=START, to_node=initializer),
            Edge(from_node=initializer, to_node=drafter),
            Edge(from_node=drafter, to_node=evaluator),
            Edge(from_node=evaluator, to_node=editor),
            Edge(from_node=editor, to_node=gate),
            Edge(from_node=gate, to_node=drafter, route="continue"),
            Edge(from_node=gate, to_node=finalizer, route="done"),
        ],
    )


def create_human_in_the_loop_workflow(settings: OrchestratorSettings | None = None) -> Any:
    """Create an ADK graph that pauses for explicit human approval."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    return _workflow(
        "human_in_the_loop_workflow",
        "ADK graph that requests human approval before final execution guidance.",
        create_context_agent(resolved_settings),
        create_approval_agent(
            resolved_settings,
            name="human_approval_agent",
            output_key="human_approval_decision",
        ),
        create_followup_agent(resolved_settings),
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
        model_role="reasoning",
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
        model_role="finalizer",
    )

    return _workflow(
        "agent_help_request_workflow",
        (
            "ADK workflow for a task-owner agent to request bounded specialist help through "
            "a broker using AgentHelpRequest and AgentHelpResponse contracts."
        ),
        task_owner,
        request_broker,
        provider,
        response_broker,
        finalizer,
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
        model_role="finalizer",
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


def _progressive_response_payload(value: Any) -> dict[str, Any]:
    """Extract one specialist response from ADK content or structured text."""

    parts = getattr(value, "parts", None) or []
    text = "".join(str(getattr(part, "text", "") or "") for part in parts)
    raw: Any = (text or value) if not isinstance(value, dict) else value
    if isinstance(raw, str):
        candidate = raw.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            candidate = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else candidate
        try:
            raw = json.loads(candidate)
        except json.JSONDecodeError:
            return {"content": candidate}
    if not isinstance(raw, dict):
        return {"content": str(raw)}
    if isinstance(raw.get("workspace"), dict) and "result" in raw:
        return _progressive_response_payload(raw["result"])
    return raw


def _progressive_publish_node(
    *,
    name: str,
    source_key: str,
    response_id: str,
    agent_name: str,
    default_role: str,
    publication_order: int,
    depends_on_response_ids: list[str],
) -> Any:
    """Publish one response immediately after its specialist completes."""

    _, FunctionNode, _, _, _ = load_workflow_classes()

    def publish(ctx: Any, node_input: Any) -> Any:
        payload = _progressive_response_payload(ctx.state.get(source_key, node_input))
        raw_metadata = payload.get("metadata")
        metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        response = AgentVisibleResponse(
            response_id=response_id,
            agent_name=agent_name,
            agent_role=str(payload.get("agent_role") or default_role),
            content=str(payload.get("content") or ""),
            depends_on_response_ids=list(depends_on_response_ids),
            visibility=(
                payload.get("visibility")
                if payload.get("visibility") in {"internal", "user_visible", "hidden"}
                else "user_visible"
            ),
            status=(
                payload.get("status")
                if payload.get("status") in {"draft", "published", "superseded", "failed"}
                else "published"
            ),
            publication_order=publication_order,
            created_at=str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
            metadata={
                **metadata,
                "workflow": "progressive_multi_agent_response",
                "state_key": "progressive_agent_responses",
                "published_incrementally": True,
            },
        ).to_dict()
        responses = [
            item.to_dict() if isinstance(item, AgentVisibleResponse) else item
            for item in list(ctx.state.get("progressive_agent_responses") or [])
            if isinstance(item, (dict, AgentVisibleResponse))
        ]
        responses = [item for item in responses if item.get("response_id") != response_id]
        responses.append(response)
        responses.sort(key=lambda item: int(item.get("publication_order", 0)))
        ctx.state["progressive_agent_responses"] = responses
        return node_input

    return FunctionNode(func=publish, name=name)


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
    llm = create_llm_specialist_factory(resolved_settings)
    visible_response_contract = _agent_visible_response_contract_template()
    required_fields = visible_response_contract["required_fields"]
    progressive_config = resolved_settings.progressive_multi_agent_response
    final_summarizer_mode = progressive_config.final_summarizer_enabled
    final_response_strategy = progressive_config.final_response_strategy

    agent_a = llm(
        name="progressive_agent_a",
        description="Analyzes requirements, constraints and operational planning.",
        instruction=f"""
        Você é o especialista independente de planejamento e requisitos no workflow
        progressive_multi_agent_response_workflow. Analise o objetivo integralmente,
        decomponha requisitos, restrições, conflitos e aspectos logísticos. Não presuma
        que outro especialista corrigirá omissões. Publique a contribuição em formato
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
        description="Independently researches evidence, costs and mathematical viability.",
        instruction=f"""
        Você é o especialista independente de pesquisa, evidências, custos e validação
        matemática. Trabalhe em paralelo ao Agente A usando somente o objetivo original;
        não dependa de progressive_response_a. Identifique dados que exigem fonte atual,
        separe fatos verificados de estimativas e confira a coerência dos cálculos.
        Publique uma contribuição no formato AgentVisibleResponse com os campos
        obrigatórios {required_fields}.

        Regras:
        - Declare explicitamente depends_on_response_ids=[] porque esta análise é
          independente e paralela ao Agente A.
        - Use response_id="response-z", agent_name="progressive_agent_b",
          visibility="user_visible", status="published" e publication_order=2.
        - Use as tools disponíveis quando o objetivo exigir evidência externa; não
          apresente estimativas como cotações verificadas.
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
        Você é o Agente C. A barreira de junção garante que progressive_response_a e
        progressive_response_b foram concluídas. Reconcilie criticamente ambas com o
        objetivo original, corrija divergências e valide que cada requisito solicitado
        aparece no resultado. Publique uma terceira contribuição no formato
        AgentVisibleResponse com os campos obrigatórios {required_fields}.

        Regras:
        - Declare depends_on_response_ids=["response-x", "response-z"], demonstrando
          que uma resposta pode depender das respostas X e Z anteriores.
        - Use response_id="response-c", agent_name="progressive_agent_c",
          visibility="user_visible", status="published" e publication_order=3.
        - Mostre claramente onde usa ou reconcilia as contribuições anteriores.
        - Não aceite cálculos inconsistentes; exponha lacunas e hipóteses remanescentes.
        - Entregue o formato solicitado pelo usuário, não apenas um resumo das respostas.
        """,
        output_key="progressive_response_c",
        tools=[fetch_http_text, extract_document_outline, inspect_json_records],
        parallel_worker=False,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    publish_a = _progressive_publish_node(
        name="publish_progressive_response_a",
        source_key="progressive_response_a",
        response_id="response-x",
        agent_name="progressive_agent_a",
        default_role="planner_specialist",
        publication_order=1,
        depends_on_response_ids=[],
    )
    publish_b = _progressive_publish_node(
        name="publish_progressive_response_b",
        source_key="progressive_response_b",
        response_id="response-z",
        agent_name="progressive_agent_b",
        default_role="research_specialist",
        publication_order=2,
        depends_on_response_ids=[],
    )
    publish_c = _progressive_publish_node(
        name="publish_progressive_response_c",
        source_key="progressive_response_c",
        response_id="response-c",
        agent_name="progressive_agent_c",
        default_role="synthesis_specialist",
        publication_order=3,
        depends_on_response_ids=["response-x", "response-z"],
    )

    Workflow, _, JoinNode, Edge, START = load_workflow_classes()
    specialists_join = JoinNode(name="progressive_specialists_join")
    edges = [
        Edge(from_node=START, to_node=agent_a),
        Edge(from_node=START, to_node=agent_b),
        Edge(from_node=agent_a, to_node=publish_a),
        Edge(from_node=agent_b, to_node=publish_b),
        Edge(from_node=publish_a, to_node=specialists_join),
        Edge(from_node=publish_b, to_node=specialists_join),
        Edge(from_node=specialists_join, to_node=agent_c),
        Edge(from_node=agent_c, to_node=publish_c),
    ]
    if final_summarizer_mode in {"enabled", "auto"}:
        final_summarizer = _create_response_chain_summarizer_agent(
            llm,
            mode=final_summarizer_mode,
            strategy=final_response_strategy,
        )
        edges.append(Edge(from_node=publish_c, to_node=final_summarizer))

    return Workflow(
        name="progressive_multi_agent_response_workflow",
        description=(
            "ADK workflow that fans out independent planning and research specialists, "
            "joins their outputs and publishes a causally linked synthesis."
        ),
        edges=edges,
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
