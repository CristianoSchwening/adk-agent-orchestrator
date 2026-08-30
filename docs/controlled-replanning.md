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
