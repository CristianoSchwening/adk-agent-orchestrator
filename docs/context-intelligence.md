# Context Intelligence — Incremento 5

O incremento 5 introduz contexto explícito antes do planejamento, mantendo os agentes e
workflows independentes de domínio.

## Fluxo

```text
objetivo
  → context_intelligence_agent
  → normalize_context_package
  → task_planner_agent
  → dispatcher
  → TaskContext mínimo por tarefa
  → agente ou workflow ADK
```

## ContextPackage

`orchestrator.context_package.v1` contém:

- objetivo preservado;
- workstream com identidade estável durante a execução;
- entidades citadas ou necessárias ao objetivo;
- restrições e terminologia específicas;
- categorias de tools potencialmente úteis.

O pacote é publicado no estado da sessão antes do Planner. O `TaskPlan` recebe o mesmo
`workstream_id`, criando rastreabilidade entre contexto, plano e execução.

## Contexto mínimo por tarefa

O dispatcher não entrega o pacote completo aos agentes. Para cada `PlannedTask`, ele cria
um `orchestrator.task_context.v1` contendo somente:

- entidades relacionadas ao texto ou às capacidades da tarefa;
- termos mencionados na tarefa;
- restrições do objetivo;
- resultados das dependências diretas;
- tools simultaneamente relevantes e realmente disponíveis no nó ADK selecionado.

Cada contexto materializado fica auditável em `task_contexts`, enquanto `context_package`
é projetado no contrato público e exibido no inspetor React.

## Tools contextuais

A seleção cruza três sinais: capacidades/tipo da tarefa, categorias sugeridas pelo
Context Intelligence e tools reais expostas pelo agente ou workflow. O resultado é uma
lista permitida e pequena no `TaskContext`; nenhuma tool inexistente é inventada.
