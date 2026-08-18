# adk-agent-orchestrator

Orquestrador multiagente construído sobre o **Google Agent Development Kit (ADK) para Python**, com SPA React, loops de verificação, monitoramento de workspace verbalizado e controles event-driven.

## Como funciona

Você envia um objetivo em texto. O `RootOrchestratorAgent` roteia para um dos sete workflows disponíveis (sequencial, paralelo, iterativo, com loop de verificação, etc.). Cada agente no caminho responde com um JSON estruturado que o `WorkspaceMonitor` valida. O resultado é um contrato versionado (`orchestrator.execution.v1`) com task, subtasks, events, métricas e respostas progressivas — consumido diretamente pela SPA React ou por qualquer cliente HTTP.

```
objetivo → router → workflow → agentes → contrato → React / API
```

Para experimentar sem chave de modelo:

```bash
npm --prefix webapp-react run build
python run_server.py
# Abra http://localhost:5000 e clique em Load Demo
```

---

## Setup completo

**Pré-requisitos:** Python `>=3.10,<3.14`, Node.js `>=18`, chave `GOOGLE_API_KEY` (ou Vertex AI).

```bash
python3.13 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -c constraints-3.13.txt -e ".[dev]"
cp .env.example .env               # configure GOOGLE_API_KEY
npm --prefix webapp-react ci
npm --prefix webapp-react run build
python run_server.py
```

Escolha `constraints-3.10.txt` a `constraints-3.13.txt` conforme sua versão do Python. O runtime é certificado para `google-adk[mcp]==2.6.1`.

**Desenvolvimento da SPA** (hot-reload):

```bash
npm --prefix webapp-react run dev   # encaminha /api para localhost:5000
```

**Via ADK CLI:**

```bash
adk run src/orchestrator
adk web --port 8000   # interface de desenvolvimento do ADK
```

---

## Workflows disponíveis

| Workflow | Primitiva ADK | Comportamento |
|---|---|---|
| `sequential` | `Workflow` em cadeia | Planner → Executor → Critic → Summarizer |
| `parallel` | fan-out + `JoinNode` | Especialistas em paralelo consolidados pelo Summarizer |
| `review_critic` | arestas condicionais | Ciclo Author ↔ Critic dentro do orçamento de iteração |
| `iterative_refinement` | arestas condicionais | Drafter → Evaluator → Editor com critério de parada por qualidade |
| `human_in_the_loop` | `Workflow` + function tool | Aprovação humana estruturada antes do follow-up |
| `progressive_multi_agent_response` | `Workflow` + DTOs | Respostas incrementais com grafo de dependência entre agentes |
| `loop2_verification` | `VerificationLoop` + rubrica | Reexecução automática até aprovação ou esgotamento do orçamento |

---

## API REST

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/status` | Status do servidor e versão do ADK |
| `POST` | `/api/run` | Executar objetivo com modelo real |
| `POST` | `/api/run/demo` | Executar objetivo em modo demo (sem modelo) |
| `GET` | `/api/loop3/config` | Configuração e histórico do EventLoop |
| `POST` | `/api/loop3/trigger` | Disparo manual do EventLoop |
| `POST` | `/api/loop3/webhook/{token}` | Disparo via webhook |
| `POST` | `/api/loop3/schedule` | Configurar agendamento cron |
| `DELETE` | `/api/loop3/schedule` | Cancelar agendamento |

Exemplo de chamada real:

```bash
curl -X POST http://localhost:5000/api/run \
  -H "Content-Type: application/json" \
  -d '{"objective": "Resumir os principais padrões de design de agentes", "workflow": "sequential"}'
```

---

## Testes e qualidade

```bash
pytest -q
ruff check src tests
python -m compileall -q src tests
python -m orchestrator.evaluation eval/datasets/phase5_smoke.json
adk-orchestrator-smoke "Validar workflows ADK"
```

CI matricial em `3.10`, `3.11`, `3.12` e `3.13` com pytest + ruff + avaliação determinística a cada push/PR.

---

## Arquitetura

```text
User / SPA React / ADK Web
          │
          ▼
RootOrchestratorAgent (ADK Workflow)
          │
          ├── workflow_router_agent (LlmAgent)
          ├── sequential_workflow
          ├── parallel_workflow (fan-out + JoinNode)
          ├── review_critic_workflow
          ├── iterative_refinement_workflow
          ├── human_in_the_loop_workflow
          ├── progressive_multi_agent_response_workflow
          ├── VerificationLoop (Loop 2)  ←→  QualityStopCondition / BudgetPolicy
          ├── EventLoop (Loop 3)         ←→  cron / webhook / manual
          ├── WorkspaceMonitor           →   verbalized_workspace traces
          ├── local tools + MCPToolset
          ├── execution contract mapper
          └── evaluation + observability
          │
          ▼
FastAPI server  ←→  React SPA
          │
          ├── ADK App + Runner
          ├── InMemorySessionService
          └── InMemoryArtifactService
```

### Módulos principais

```text
src/orchestrator/
├── agent.py              # módulo de descoberta do ADK (root_agent)
├── config.py             # OrchestratorSettings + cesta de modelos
├── server.py             # FastAPI + endpoints REST
├── agents/               # root, specialists, workflows ADK
├── loops/                # VerificationLoop (L2), EventLoop (L3), rubric, stop_condition
├── workspace/            # WorkspaceMonitor, VerbalizedWorkspace, FileWorkspaceRepository
├── contracts/dto.py      # DTOs do contrato orchestrator.execution.v1
├── mapping/adk.py        # mapper ADK Session → contrato
├── tools/                # tools locais, catálogo, métricas, MCP factory
├── evaluation/           # runner determinístico + critérios
├── observability/gcp.py  # logs/métricas JSON para Google Cloud
├── policies/budget.py    # BudgetPolicy para loops ADK
└── runner/bootstrap.py   # App + Runner + serviços in-memory
```

---

## Funcionalidades em detalhe

### Loop 2 — Verificação por rubrica

`VerificationLoop` avalia saídas contra uma rubrica ponderada (completeness, clarity, accuracy, actionability). Cada iteração pontua, marca respostas anteriores como *superseded* e solicita refinamento. `QualityStopCondition` implementa `should_stop_loop` do ADK combinando o grader com `BudgetPolicy` (iterações, chamadas de modelo, tempo).

### Loop 3 — Event-Driven

`EventLoop` expõe três formas de acionar o agente: **manual** (`POST /api/loop3/trigger`), **webhook** (`POST /api/loop3/webhook/{token}`) e **cron** (agendamento configurável, mínimo 10 s). Histórico das últimas 20 execuções disponível em `GET /api/loop3/config`.

### Workspace verbalizado

`WorkspaceMonitor` exige que cada agente responda com `{ "workspace": {...}, "result": "..." }`. Snapshots versionados (`orchestrator.verbalized_workspace.v1`) são gravados em `observability/verbalized_workspace/traces/`. Em modo `strict` (padrão), resposta inválida encerra o agente com lifecycle `violation → failed`. Em modo `audit`, a violação é registrada sem interromper.

### Contrato de execução

O mapper em `src/orchestrator/mapping/adk.py` projeta `ADK Session / Events / Artifacts` no contrato `orchestrator.execution.v1`:

```
task · subtasks · events · metrics · decision_metadata · artifacts · progressive_agent_responses
```

Snapshot de exemplo: [`docs/contracts/execution_contract_v1.example.json`](docs/contracts/execution_contract_v1.example.json).

### SPA React

Servida pelo FastAPI em `/`. Inclui Chat view, DAG view, Execution Inspector, Event Log, Event Loop panel (Loop 3) e theme toggle. Stack: Vite + Tailwind + shadcn/ui.

---

## Configuração avançada

### Cesta de modelos

```bash
ADK_MODEL="gemini-flash-latest"           # modelo base
ADK_MODEL_ROUTER="gemini-2.0-flash"
ADK_MODEL_REASONING="gemini-2.0-flash"    # críticos e avaliadores
ADK_MODEL_WORKER="gemini-flash-latest"    # planejadores e executores
ADK_MODEL_FINALIZER="gemini-2.0-flash"    # sumarizadores
ADK_MODEL_FALLBACK="gemini-flash-latest"  # fallback após circuit break
```

Erros `429` e `503` após retries ativam um circuit breaker em memória; chamadas seguintes usam `ADK_MODEL_FALLBACK` até o processo reiniciar.

### Retry de modelo

```bash
ADK_MODEL_RETRY_ATTEMPTS="4"
ADK_MODEL_RETRY_INITIAL_DELAY_SECONDS="1"
ADK_MODEL_RETRY_MAX_DELAY_SECONDS="8"
ADK_MODEL_RETRY_EXPONENTIAL_BASE="2"
ADK_MODEL_RETRY_JITTER_SECONDS="1"
```

### Tools e MCP

```bash
ADK_TOOL_TIMEOUT_SECONDS="10"
ADK_MCP_SERVERS='[{"name":"filesystem","transport":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","."]}]'
```

### Workspace verbalizado

```bash
ADK_WORKSPACE_ENABLED="true"
ADK_WORKSPACE_MODE="strict"           # strict | audit
ADK_WORKSPACE_ROOT="observability/verbalized_workspace/traces"
ADK_WORKSPACE_MAX_BYTES="65536"
```

### Progressive multi-agent response

```bash
ADK_PROGRESSIVE_FINAL_SUMMARIZER_ENABLED="disabled"   # enabled | disabled | auto
ADK_PROGRESSIVE_FINAL_RESPONSE_STRATEGY="all_visible_responses"
# last_agent_response | summarizer_response | root_selected_response | all_visible_responses
```

---

## Documentação adicional

- [`docs/architecture.md`](docs/architecture.md) — decisões arquiteturais e fluxo de execução
- [`docs/tools.md`](docs/tools.md) — catálogo de tools e configuração MCP
- [`docs/evaluation.md`](docs/evaluation.md) — critérios e datasets de avaliação
- [`docs/observability.md`](docs/observability.md) — logs e métricas para Google Cloud
- [`docs/contracts/README.md`](docs/contracts/README.md) — contrato de execução versionado
- [`docs/runbooks/`](docs/runbooks/) — runbooks de incidente, rollback e atualização de agentes
