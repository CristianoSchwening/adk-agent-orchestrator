# Contrato de execução — Fase 4

A Fase 4 define um contrato JSON versionado para clientes Web, Android, CLI ou API. A orquestração permanece no backend ADK Python; clientes consomem apenas DTOs estáveis.

## Versão atual

- `contract_version`: `orchestrator.execution.v1`
- Snapshot: [`execution_contract_v1.example.json`](execution_contract_v1.example.json)

## Campos principais

| Campo | Descrição |
| --- | --- |
| `task` | Identidade, objetivo, status, sessão ADK e resposta final. |
| `run_id` | Identificador estável da execução consultável e retomável pela API. |
| `human_requests` | Solicitações humanas e respectivas respostas, renderizadas na conversa. |
| `subtasks` | Projeção de etapas/workflow/subagentes para timelines de UI. |
| `events` | Eventos ADK normalizados com tipo, fonte, mensagem, timestamp e severidade. |
| `metrics` | Contadores de eventos, subtasks, artifacts, tools, modelo e erros. |
| `decision_metadata` | Workflow selecionado, racional, confiança, alternativas e versão de policy. |
| `artifacts` | Referências a artifacts ADK ou outputs persistidos. |
| `progressive_agent_responses` | Mensagens de especialistas que podem aparecer no chat com autoria (`agent_name`/`agent_role`), ordem (`publication_order`) e causalidade (`depends_on_response_ids`). |

## Interação humana

`task.status` pode ser `awaiting_human`: a execução está pausada e não há resposta final.
Cada item de `human_requests` identifica a solicitação, a tarefa e a tentativa, a candidata,
os critérios, o tipo (`approval` ou `clarification`) e seu estado (`pending` ou `answered`).
Solicitações respondidas incluem decisão, comentário, origem humana e data. Clientes antigos
podem ignorar os campos adicionais; os novos clientes devem usar `human_requests ?? []`.

`GET /api/runs/{run_id}` recupera o contrato persistido. Para continuar a mesma sessão,
envie `POST /api/runs/{run_id}/human-requests/{request_id}/response` com `decision`,
`comment` e `idempotency_key`. As decisões são `approved`, `rejected`, `needs_changes`
e `clarification`; as três últimas exigem comentário. O tipo da decisão deve corresponder
ao tipo da solicitação. Use uma chave estável durante os reenvios (a interface usa o próprio
`request_id`). Um reenvio igual não repete ações; resposta diferente ou solicitação obsoleta
retorna 409. A decisão é persistida antes da continuação, e uma trava por execução impede
retomadas concorrentes entre processos.

As sessões/eventos ADK e os snapshots da execução são guardados em `data/executions`
por padrão (pasta irmã de `task_run_root`). A identidade vem da configuração do servidor,
não do corpo enviado pelo navegador. Este servidor mantém o modelo local de usuário único
existente; essas rotas não substituem autenticação para exposição multiusuário.

Esclarecimentos são explicitamente configurados em `task.metadata.human_input_kind`
(`clarification`) e `human_question`. Se a tarefa também exigir aprovação, a informação
fornecida gera uma nova proposta e uma nova solicitação de aprovação; esclarecer não
autoriza ações protegidas. Rejeição encerra a execução como `cancelled`, sem replanejar
para contornar a decisão.

## Referência do legado

O contrato se inspira no legado `meu-orquestrador`, que retornava task, subtarefas, eventos, modo/status e contexto de execução. A implementação nova não porta `Workforce`, `TaskBoard` ou `Subtask`; ela mapeia ADK `Session`, eventos e artifacts para DTOs próprios do backend greenfield.

## Consumo por frontend futuro

Um webapp futuro deve:

1. Chamar uma API/CLI que retorne `ExecutionContractDTO.to_dict()`.
2. Renderizar `task.status` e `task.final_response` no cabeçalho.
3. Renderizar `subtasks` como timeline ou kanban de etapas.
4. Renderizar `events` como log streaming/histórico.
5. Renderizar `metrics` e `decision_metadata` em painéis de auditoria.
6. Renderizar `progressive_agent_responses` como mensagens de chat sucessivas quando o workflow selecionado for `progressive_multi_agent_response`; usar `response_id` e `depends_on_response_ids` para mostrar dependências entre contribuições.
7. Usar `contract_version` para compatibilidade e migrações.

## Respostas progressivas de especialistas

O modo `progressive_multi_agent_response` é separado de `agent_help_request`: ele não representa ajuda pontual brokerada entre agentes. Ele modela uma experiência de chat em que especialistas publicam contribuições sucessivas ao usuário. O estado ADK usa a chave `progressive_agent_responses`, e o contrato público expõe uma lista de `AgentVisibleResponse` com `response_id`, `agent_name`, `agent_role`, `content`, `depends_on_response_ids`, `visibility`, `status`, `publication_order`, `created_at` e `metadata`. Assim, o frontend pode mostrar que a resposta Z depende da resposta X e que a resposta C depende de múltiplas respostas anteriores.
