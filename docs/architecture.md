# Arquitetura — Fase 1 ADK Python

## Objetivo

Criar a base de um novo repositório ADK-only, sem reaproveitar o código do orquestrador atual.

## Escopo implementado

```text
┌────────────────────┐
│ Entrada do usuário │
└─────────┬──────────┘
          │
          ▼
┌────────────────────────────┐
│ RootOrchestratorAgent      │
│ - Agent ADK                │
│ - tools mínimas            │
│ - instruções de bootstrap  │
└─────────┬──────────────────┘
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
┌──────────────┐ ┌─────────────────┐
│ SessionService│ │ ArtifactService │
│ InMemory      │ │ InMemory        │
└──────────────┘ └─────────────────┘
```

## Decisões arquiteturais

1. **ADK como runtime central**: o bootstrap usa `Runner`, `Agent`, `InMemorySessionService` e `InMemoryArtifactService`.
2. **Sem código legado**: não há dependência de `workforce.py`, `TaskBoard`, `Subtask` ou `Toolkit`.
3. **Lazy imports do ADK**: os módulos de domínio podem ser testados mesmo quando o wheel `google-adk` não está instalado no interpretador local.
4. **Persistência in-memory**: adequada à Fase 1; fases futuras devem avaliar serviços persistentes.
5. **Configuração por ambiente**: `ADK_APP_NAME`, `ADK_USER_ID` e `ADK_MODEL` são lidos de variáveis de ambiente.

## Fluxo de execução

```text
orchestrator.main
   │
   ▼
run_once(objective)
   │
   ├── build_runtime()
   │     ├── create_root_agent()
   │     ├── InMemorySessionService()
   │     ├── InMemoryArtifactService()
   │     └── Runner(...)
   │
   ├── session_service.create_session(...)
   ├── runner.run_async(...)
   └── resposta final
```

## Fora do escopo da Fase 1

- Workflows multiagente.
- DAGs complexos.
- Human-in-the-loop.
- Adapter de contrato para UI.
- Persistência distribuída.
- Observabilidade de produção.
