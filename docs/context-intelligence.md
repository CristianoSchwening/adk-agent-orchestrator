# Context Intelligence — Incremento 5

O incremento 5 introduz contexto explícito antes do planejamento, mantendo os agentes e
workflows independentes de domínio.

## Fluxo

```text
objetivo
  → UserProfile persistente
  → attach_user_profile_context
  → context_intelligence_agent
  → normalize_context_package
  → task_planner_agent
  → dispatcher
  → TaskContext mínimo por tarefa
  → agente ou workflow ADK
```

## ContextPackage

`orchestrator.context_package.v2` contém:

- objetivo preservado;
- `UserProfile` estável e independente do workstream;
- workstream com identidade estável durante a execução;
- entidades citadas ou necessárias ao objetivo;
- restrições e terminologia específicas;
- categorias de tools potencialmente úteis.

O pacote é publicado no estado da sessão antes do Planner. O `TaskPlan` recebe o mesmo
`workstream_id`, criando rastreabilidade entre contexto, plano e execução.

## Contexto mínimo por tarefa

O dispatcher não entrega o pacote completo aos agentes. Para cada `PlannedTask`, ele cria
um `orchestrator.task_context.v2` contendo somente:

- entidades relacionadas ao texto ou às capacidades da tarefa;
- termos mencionados na tarefa;
- restrições do objetivo;
- preferências, idioma, fuso e restrições persistentes do usuário;
- resultados das dependências diretas;
- tools simultaneamente relevantes e realmente disponíveis no nó ADK selecionado.

Cada contexto materializado fica auditável em `task_contexts`, enquanto `context_package`
é projetado no contrato público e exibido no inspetor React.

## Tools contextuais

A seleção cruza três sinais: capacidades/tipo da tarefa, categorias sugeridas pelo
Context Intelligence e tools reais expostas pelo agente ou workflow. O resultado é uma
lista permitida e pequena no `TaskContext`; nenhuma tool inexistente é inventada.

## UserProfile editável

O perfil padrão fica em `config/user-profile.json`, podendo ser editado diretamente no
GitHub. Ele contém identidade funcional, papel, organização, idioma, fuso, áreas de
experiência, preferências e restrições. Não armazene segredos, tokens ou dados sensíveis.

O caminho pode ser alterado por `ADK_USER_PROFILE_PATH`. O arquivo precisa permanecer
dentro do repositório. Quando ausente, a execução continua sem perfil para preservar
compatibilidade com outros ambientes.
