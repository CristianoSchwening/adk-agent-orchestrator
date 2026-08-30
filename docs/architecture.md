# Arquitetura — Fase 5 ADK Python

## Objetivo

Implementar workflows multiagente, tools/MCP, contrato UI/API e readiness de avaliação/produção usando somente primitivas oficiais do Google ADK Python, mantendo o repositório greenfield e sem reaproveitar o runtime legado.

## Escopo implementado

```text
┌────────────────────┐
│ Entrada do usuário │
└─────────┬──────────┘
          │
          ▼
┌───────────────────────────────┐
│ RootOrchestratorAgent         │
│ - Workflow graph ADK          │
│ - LlmAgent roteador           │
│ - tools de status/captura     │
│ - workflows aninhados         │
│ - tools locais e MCP toolsets  │
│ - contrato UI/API versionado   │
│ - avaliação e observabilidade  │
└─────────┬─────────────────────┘
          │
          ├── sequential_workflow
          │   └── Workflow: planner → executor → critic → summarizer
          │
          ├── parallel_workflow
          │   └── fan-out + JoinNode: especialistas em paralelo
          │
          ├── review_critic_workflow
          │   └── Workflow: author ↔ critic por aresta condicional
          │
          ├── iterative_refinement_workflow
          │   └── Workflow: drafter → evaluator → editor por aresta condicional
          │
          └── human_in_the_loop_workflow
              └── Workflow: context → approval tool → follow-up
          │
          ▼
┌────────────────────────────┐
│ App + Runner ADK           │
│ - App(name, root_agent)    │
│ - session_service          │
│ - artifact_service         │
└─────┬───────────────┬──────┘
      │               │
      ▼               ▼
┌───────────────┐ ┌─────────────────┐
│ SessionService│ │ ArtifactService │
│ InMemory      │ │ InMemory        │
└───────────────┘ └─────────────────┘
```

## Agentes especialistas e workflows ADK da Fase 2

Os agentes especialistas ficam em `src/orchestrator/agents/specialists.py` e os workflows ficam em `src/orchestrator/agents/workflows.py`. Essa separação preserva o ponto forte conceitual do legado — agente/toolkit/subtask/execução com papéis claros — sem reintroduzir `Workforce`, `TaskBoard` ou `Subtask`.

Especialistas disponíveis: planner, executor, critic, summarizer, researcher, refiner e approval agent.

## Workflows ADK da Fase 2

| Workflow | Primitiva ADK | Papel |
| --- | --- | --- |
| `sequential` | `Workflow` em cadeia | Planejar, executar, criticar e resumir em ordem determinística. |
| `parallel` | `Workflow` com fan-out + `JoinNode` | Rodar especialistas em paralelo e consolidar com Summarizer. |
| `review_critic` | `Workflow` com rota condicional | Alternar autoria e crítica dentro do orçamento de iteração. |
| `iterative_refinement` | `Workflow` com rota condicional | Criar rascunho, avaliar e refinar iterativamente. |
| `human_in_the_loop` | `Workflow` + function tool ADK | Registrar decisão humana estruturada antes do follow-up. |

O workflow `parallel` segue o desenho original do legado reinterpretado em ADK:

```text
parallel_workflow (Workflow)
├── fan-out: planner + researcher + executor
├── parallel_specialists_join (JoinNode)
└── parallel_summarizer_agent
```

Esses workflows são preservados como exemplos didáticos autocontidos. A camada de dispatch
por estratégia é apenas uma composição adicional: ela usa `ctx.run_node()` do ADK para
executar a factory existente adequada à estratégia de cada `PlannedTask`. Portanto, os
fluxos continuam utilizáveis e testáveis de forma independente do Root Orchestrator.

| Estratégia da tarefa | Nó ADK executado |
| --- | --- |
| `single_agent` | Especialista escolhido por capacidades |
| `sequential` | `sequential_workflow` |
| `parallel` | `parallel_workflow` com fan-out e `JoinNode` |
| `review_critic` | `review_critic_workflow` |
| `iterative_refinement` | `iterative_refinement_workflow` |
| `human_in_the_loop` | `human_in_the_loop_workflow` |
| `verification` | `review_critic_workflow`, preservando a intenção no `TaskRun` |

## Tools e MCP da Fase 3

A Fase 3 adiciona um catálogo de tools locais e desejadas, function tools seguras para filesystem/HTTP/documentos/dados/modelo e uma factory lazy para `MCPToolset`. Timeouts, erros padronizados e métricas process-local ficam em `src/orchestrator/tools/`.

## Contrato de execução da Fase 4

A Fase 4 adiciona DTOs versionados em `src/orchestrator/contracts/dto.py` e um mapper em `src/orchestrator/mapping/adk.py`. O contrato `orchestrator.execution.v1` projeta ADK Session, Events e Artifacts para `task`, `subtasks`, `events`, `metrics`, `decision_metadata` e `artifacts`, mantendo clientes Web/Android desacoplados da orquestração interna.

## Avaliação e produção da Fase 5

A Fase 5 adiciona datasets em `eval/datasets/`, runner determinístico em `src/orchestrator/evaluation/`, workflow de CI em `.github/workflows/evaluation.yml`, observabilidade JSON compatível com Google Cloud em `src/orchestrator/observability/` e runbooks em `docs/runbooks/`.

## Decisões arquiteturais

1. **ADK como runtime central**: o bootstrap usa `App`, `Runner`, `LlmAgent`, `Workflow`, `FunctionNode`, `JoinNode`, ADK function tools, MCP Toolsets e serviços in-memory.
2. **Sem código legado**: não há dependência de `workforce.py`, `TaskBoard`, `Subtask` ou `Toolkit`.
3. **Lazy imports do ADK**: os módulos de domínio podem ser testados mesmo quando o wheel `google-adk` não está instalado no interpretador local.
4. **Root como grafo**: um `LlmAgent` escolhe a rota, um `FunctionNode` normaliza a saída e arestas condicionais acionam exatamente um workflow aninhado.
5. **Persistência in-memory**: adequada ao desenvolvimento local; fases futuras devem avaliar serviços persistentes.
6. **Configuração por ambiente**: `ADK_APP_NAME`, `ADK_USER_ID`, `ADK_MODEL`, `ADK_TOOL_TIMEOUT_SECONDS` e `ADK_MCP_SERVERS` são lidos de variáveis de ambiente.
7. **Contrato versionado**: clientes consomem `orchestrator.execution.v1`; mudanças futuras devem criar nova versão ou mapper compatível.
8. **Readiness de produção**: avaliações determinísticas rodam sem credenciais; logs e métricas são emitidos como JSON compatível com Cloud Logging/Monitoring.

## Fluxo de execução

```text
orchestrator.main
   │
   ▼
run_once(objective)
   │
   ├── build_runtime()
   │     ├── create_root_agent()
   │     │    └── create_phase2_workflows()
   │     ├── App(name, root_agent)
   │     ├── InMemorySessionService()
   │     ├── InMemoryArtifactService()
   │     └── Runner(app=...)
   │
   ├── session_service.create_session(..., state={"phase": "phase_5_evaluation_production", "contract_version": "orchestrator.execution.v1", ...})
   ├── runner.run_async(...)
   └── resposta final
```

## Fora do escopo da Fase 2

- Runtime customizado ou DAG scheduler próprio.
- Persistência distribuída.
- Adapter completo de contrato para UI.
- Observabilidade de produção.
- Callbacks avançados de interrupção/continuação além da composição ADK básica.
