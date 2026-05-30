# Contrato de execução — Fase 4

A Fase 4 define um contrato JSON versionado para clientes Web, Android, CLI ou API. A orquestração permanece no backend ADK Python; clientes consomem apenas DTOs estáveis.

## Versão atual

- `contract_version`: `orchestrator.execution.v1`
- Snapshot: [`execution_contract_v1.example.json`](execution_contract_v1.example.json)

## Campos principais

| Campo | Descrição |
| --- | --- |
| `task` | Identidade, objetivo, status, sessão ADK e resposta final. |
| `subtasks` | Projeção de etapas/workflow/subagentes para timelines de UI. |
| `events` | Eventos ADK normalizados com tipo, fonte, mensagem, timestamp e severidade. |
| `metrics` | Contadores de eventos, subtasks, artifacts, tools, modelo e erros. |
| `decision_metadata` | Workflow selecionado, racional, confiança, alternativas e versão de policy. |
| `artifacts` | Referências a artifacts ADK ou outputs persistidos. |

## Referência do legado

O contrato se inspira no legado `meu-orquestrador`, que retornava task, subtarefas, eventos, modo/status e contexto de execução. A implementação nova não porta `Workforce`, `TaskBoard` ou `Subtask`; ela mapeia ADK `Session`, eventos e artifacts para DTOs próprios do backend greenfield.

## Consumo por frontend futuro

Um webapp futuro deve:

1. Chamar uma API/CLI que retorne `ExecutionContractDTO.to_dict()`.
2. Renderizar `task.status` e `task.final_response` no cabeçalho.
3. Renderizar `subtasks` como timeline ou kanban de etapas.
4. Renderizar `events` como log streaming/histórico.
5. Renderizar `metrics` e `decision_metadata` em painéis de auditoria.
6. Usar `contract_version` para compatibilidade e migrações.
