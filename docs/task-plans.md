# Planos de tarefas — Incremento 1

O Incremento 1 introduz o contrato `orchestrator.task_plan.v1` para representar objetivos,
entregáveis e tarefas generalistas como um grafo direcionado acíclico (DAG). Nesta etapa,
os planos são criados, validados, persistidos e exibidos, mas ainda não são executados
dinamicamente pelo dispatcher.

## Modelo

Cada plano contém:

- um objetivo normalizado, restrições e critérios globais de sucesso;
- um ou mais entregáveis;
- tarefas com tipo, capacidades requeridas e critérios de aceite;
- dependências entre tarefas;
- uma estratégia conhecida por tarefa;
- metadados de versão e revisão.

O modelo é independente de domínio. Ele pode representar desenvolvimento de software,
pesquisa, análise, planejamento, criação de documentos e outros tipos de trabalho.

## Validação

Antes de persistir ou publicar um plano, o backend verifica:

- versão de schema suportada;
- identificadores obrigatórios e únicos;
- presença de objetivo, tarefas, entregáveis e critérios de aceite;
- referências de dependência existentes;
- ausência de autorreferência e ciclos;
- existência de tarefas iniciais e terminais;
- limite de 50 tarefas por plano.

## Persistência

Os planos são armazenados, por padrão, em `data/task_plans/<plan_id>.json`. A escrita usa
arquivo temporário e substituição atômica. Identificadores que possam escapar do diretório
configurado são rejeitados.

Configuração:

```bash
ADK_TASK_PLAN_ROOT="data/task_plans"
ADK_TASK_PLAN_MAX_BYTES="262144"
```

## API

Criar e validar um plano:

```http
POST /api/task-plans
Content-Type: application/json
```

Consultar um plano:

```http
GET /api/task-plans/{plan_id}
```

O contrato de execução aceita um campo opcional `task_plan`. Clientes anteriores continuam
compatíveis porque o restante de `orchestrator.execution.v1` não foi removido ou renomeado.

## Planner assistido por LLM

O Incremento 2 adiciona `task_planner_agent`, um `LlmAgent` oficial do ADK com
`output_schema` dedicado. Ele produz somente um rascunho estrutural, sem metadados de
persistência. Um `FunctionNode` ADK materializa IDs de plano, versão, timestamps e status,
executa o mesmo validador determinístico do Incremento 1 e publica o plano no estado da
sessão como `task_plan`.

O fluxo automático passa a ser:

```text
LlmAgent(task_planner_agent)
  → FunctionNode(normalize_task_plan)
  → LlmAgent(workflow_router_agent)
  → workflow ADK selecionado
```

Quando o cliente escolhe explicitamente um workflow, o mesmo estágio de planejamento é
executado antes daquele workflow. Planos válidos são persistidos pelo repositório JSON ao
final da execução e projetados no contrato público.

O planner cria tarefas, mas não as executa, não seleciona agentes e não implementa um
scheduler próprio. Essas responsabilidades permanecem reservadas ao futuro dispatcher.

## Próximos incrementos

O dispatcher futuro consumirá somente planos que tenham passado pelo validador determinístico.
