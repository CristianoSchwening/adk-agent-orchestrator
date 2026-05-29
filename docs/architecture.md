# Arquitetura — Fase 2 ADK Python

## Objetivo

Implementar workflows multiagente equivalentes usando somente primitivas oficiais do Google ADK Python, mantendo o repositório greenfield e sem reaproveitar o runtime legado.

## Escopo implementado

```text
┌────────────────────┐
│ Entrada do usuário │
└─────────┬──────────┘
          │
          ▼
┌───────────────────────────────┐
│ RootOrchestratorAgent         │
│ - LlmAgent ADK                │
│ - tools de status/captura     │
│ - subagentes de workflow ADK  │
└─────────┬─────────────────────┘
          │
          ├── sequential_workflow
          │   └── SequentialAgent: planner → executor → critic → summarizer
          │
          ├── parallel_workflow
          │   └── ParallelAgent: architecture + quality + risk specialists
          │
          ├── review_critic_workflow
          │   └── LoopAgent: author ↔ critic
          │
          ├── iterative_refinement_workflow
          │   └── LoopAgent: drafter → evaluator → editor
          │
          └── human_in_the_loop_workflow
              └── SequentialAgent: context → approval tool → follow-up
          │
          ▼
┌────────────────────────────┐
│ Runner ADK                 │
│ - app_name                 │
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

## Workflows ADK da Fase 2

| Workflow | Primitiva ADK | Papel |
| --- | --- | --- |
| `sequential` | `SequentialAgent` | Planejar, executar, criticar e resumir em ordem determinística. |
| `parallel` | `ParallelAgent` | Rodar especialistas independentes para arquitetura, qualidade e risco. |
| `review_critic` | `LoopAgent` | Alternar autoria e crítica dentro do orçamento de iteração. |
| `iterative_refinement` | `LoopAgent` | Criar rascunho, avaliar e refinar iterativamente. |
| `human_in_the_loop` | `SequentialAgent` + function tool ADK | Registrar decisão humana estruturada antes do follow-up. |

## Decisões arquiteturais

1. **ADK como runtime central**: o bootstrap usa `Runner`, `LlmAgent`, `SequentialAgent`, `ParallelAgent`, `LoopAgent`, `InMemorySessionService` e `InMemoryArtifactService`.
2. **Sem código legado**: não há dependência de `workforce.py`, `TaskBoard`, `Subtask` ou `Toolkit`.
3. **Lazy imports do ADK**: os módulos de domínio podem ser testados mesmo quando o wheel `google-adk` não está instalado no interpretador local.
4. **Workflows como subagentes**: o agente raiz recebe os workflows como subagentes ADK, permitindo delegação pelo mecanismo nativo do ADK.
5. **Persistência in-memory**: adequada ao desenvolvimento local; fases futuras devem avaliar serviços persistentes.
6. **Configuração por ambiente**: `ADK_APP_NAME`, `ADK_USER_ID` e `ADK_MODEL` são lidos de variáveis de ambiente.

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
   │     ├── InMemorySessionService()
   │     ├── InMemoryArtifactService()
   │     └── Runner(...)
   │
   ├── session_service.create_session(..., state={"phase": "phase_2_adk_workflows"})
   ├── runner.run_async(...)
   └── resposta final
```

## Fora do escopo da Fase 2

- Runtime customizado ou DAG scheduler próprio.
- Persistência distribuída.
- Adapter completo de contrato para UI.
- Observabilidade de produção.
- Callbacks avançados de interrupção/continuação além da composição ADK básica.
