# Replanejamento controlado — Incremento 6

O incremento 6 permite corrigir o curso de uma execução sem transformar o orquestrador
em um planejador instável. O plano vigente só pode ser substituído por uma nova revisão
quando ocorre um dos cinco gatilhos autorizados:

- falha de tarefa (`task_failed`);
- bloqueio (`blocker_detected`);
- premissa invalidada (`assumption_invalidated`);
- nova informação que muda o objetivo (`objective_changed`);
- resultado que não satisfaz os critérios (`acceptance_criteria_failed`).

Falhas e ausência de tarefas prontas são detectadas deterministicamente pelo dispatcher.
Após uma execução bem-sucedida, um guardião LLM estruturado avalia premissas, mudanças
de objetivo e critérios de aceitação. Solicitações externas usam o mesmo modelo validado
`ReplanRequest`; qualquer valor fora da lista é rejeitado antes de acionar o LLM.

## Versionamento e histórico

Cada replanejamento produz um novo `plan_id`, incrementa `revision`, mantém `lineage_id`
e referencia o plano anterior em `parent_plan_id`. Plano e execução anteriores são
preservados em `task_plan_history` e `task_run_history`, além dos arquivos imutáveis nos
repositórios de planos e execuções. O contrato e o inspetor exibem a revisão vigente,
o gatilho e a quantidade de versões anteriores.

O limite padrão é de duas revisões por execução e pode ser configurado com
`ADK_MAX_REPLANS`. Ao atingir o limite, o estado recebe `replan_status=limit_exhausted`
e a execução falha explicitamente, evitando ciclos sem fim.

## Componentes ADK

O guardião e o replanejador são agentes ADK com saída estruturada. O dispatcher continua
como `FunctionNode`, usando `run_node` para delegar as decisões sem criar uma camada de
execução paralela ao ADK. Todos os workflows didáticos existentes permanecem disponíveis.


## Persisted acceptance diagnostics

Task-run v2 records now include additive, optional diagnostics. Existing records remain
readable: `output_status: not_recorded` means no diagnostic was captured, not empty output.

- `execution_output` is saved atomically before invoking the acceptance guard.
- `output_status` distinguishes `absent` (None), `empty` (blank text/empty list or object)
  and `present`; `output_recorded_at` records when the output was captured.
- `evaluation` stores the trigger, rationale, criterion catalog and a decision for every
  criterion (`passed`, `failed`, `unverifiable`), with rationale and evidence.
- Criterion IDs are SHA-256 hashes of exact criterion text, stable across reordering and
  plan revisions that keep that text. Identical criteria share one catalog entry.
- `evaluated_at` records evaluation completion; `evaluation_error` records evaluator
  exceptions or invalid responses. Such failures terminate with `evaluation_failed`,
  without incorrectly requesting a content replan.
- `result` retains its existing meaning: accepted output only. Rejected content remains
  in `execution_output`, including when the replan limit is exhausted.

The guard must cover every catalog ID exactly once. Unknown/duplicate/missing IDs,
invalid triggers and contradictory approval decisions are rejected locally.
Diagnostics use the existing task-run repository and its size limit; they are not
silently truncated. Output and evidence can contain task data, so apply the same access
controls as for existing run results. The inspector section “Avaliações e tentativas” displays the current run and prior
revisions, criterion rationale/evidence, evaluator errors and expandable output. Legacy
records explicitly display “Diagnóstico não registrado”. Output is rendered as escaped
text, never HTML.

Replan requests now include the rejected output, output status and full evaluation.
The replanner also receives previous criterion evaluations to identify recurring failures;
its instructions require concrete corrections without weakening acceptance criteria. The
next execution of the same task ID receives the most recent failed attempt as
`previous_attempt`. New task IDs have no automatic prior-attempt match.

Each failed run stores its `replan_request` before calling the replanner. Successor runs
store `parent_run_id`. On exhaustion, `terminal_error` stores
`replan_limit_exhausted`, configured `limit`, `used` revisions and a timestamp, while
preserving the last request and evaluation. The execution contract already carries the
run and plan histories, so no new API endpoint is needed.

Validation: `pytest -q`, `ruff check src tests`, `npm --prefix webapp-react test` and
`npm --prefix webapp-react run build`. Frontend tests render real React components with
Vite SSR and cover legacy data, failure categories, histories and escaped output.
