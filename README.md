# adk-agent-orchestrator

Repositório **greenfield** para a reimplementação do orquestrador usando **Google Agent Development Kit (ADK) para Python**.

Esta entrega implementa a **Fase 5 — Avaliação e Produção** sobre o contrato UI/API da Fase 4:

- `RootOrchestratorAgent` como grafo `Workflow`, com roteador LLM e workflows aninhados.
- `App` e `Runner` oficiais do ADK.
- `InMemorySessionService` para sessões locais.
- `InMemoryArtifactService` para artefatos locais.
- Configuração por `.env`/variáveis de ambiente.
- Workflows equivalentes usando apenas primitivas ADK Python:
  - `Workflow` em cadeia para Planner → Executor → Critic → Summarizer.
  - `Workflow` com fan-out e `JoinNode` para especialistas em paralelo.
  - `Workflow` com arestas condicionais para `review_critic` e `iterative_refinement`.
  - `Workflow` em cadeia com tool ADK para `human_in_the_loop`.
- Tools locais seguras para filesystem, HTTP, documentos, dados e planejamento de modelo.
- Catálogo de tools consultável pelo agente raiz.
- Factory lazy para integração externa via ADK `MCPToolset`.
- Timeouts, erros padronizados e métricas locais de uso de tools.
- Contrato JSON versionado `orchestrator.execution.v1` para UI/API.
- DTOs para task, subtasks, events, metrics, decision_metadata e artifacts.
- Mapper de ADK Session/Events/Artifacts para contrato de execução.
- Snapshot JSON em `docs/contracts/` para consumidores Web/Android/API.
- Datasets determinísticos de avaliação em `eval/datasets/`.
- Critérios de qualidade, segurança, custo e latência.
- Workflow de CI para testes, lint, compileall e avaliação.
- Observabilidade com logs/metric payloads compatíveis com Google Cloud.
- Runbooks de incidente, rollback e atualização de agentes.
- Testes de smoke para configuração, tools, contrato, avaliação, políticas e workflows.

> A implementação não reaproveita runtime legado (`Workforce`, `TaskBoard` ou `Subtask`). O novo desenho parte das primitivas oficiais do ADK Python.

## Arquitetura da Fase 5

```text
User / CLI / ADK Web
        │
        ▼
RootOrchestratorAgent (ADK Workflow)
        │
        ├── capture_objective tool
        ├── get_orchestrator_status tool
        ├── workflow_router_agent (ADK LlmAgent)
        ├── sequential_workflow (ADK Workflow)
        ├── parallel_workflow (fan-out + JoinNode)
        ├── review_critic_workflow (arestas condicionais)
        ├── iterative_refinement_workflow (arestas condicionais)
        ├── human_in_the_loop_workflow (ADK Workflow + tool)
        ├── Phase 3 local tools + MCP toolsets
        ├── Phase 4 execution contract mapper
        └── Phase 5 evaluation + observability readiness
        │
        ▼
ADK App + Runner
        │
        ├── InMemorySessionService
        └── InMemoryArtifactService
```

## Estrutura

```text
adk-agent-orchestrator/
├── pyproject.toml
├── .env.example
├── src/orchestrator/
│   ├── agent.py                 # módulo de descoberta do ADK com root_agent
│   ├── agents/root.py           # factory do RootOrchestratorAgent
│   ├── agents/specialists.py    # factories dos agentes especialistas
│   ├── agents/workflows.py      # composição dos workflows ADK da Fase 2
│   ├── runner/bootstrap.py      # App + Runner + SessionService + ArtifactService
│   ├── tools/foundation.py      # tools de status/captura
│   ├── tools/human.py           # tool de aprovação humana
│   ├── tools/local.py           # tools locais da Fase 3
│   ├── tools/catalog.py         # catálogo de tools
│   ├── tools/metrics.py         # métricas de uso de tools
│   ├── mcp/factory.py           # factory lazy para MCPToolset
│   ├── contracts/dto.py         # DTOs versionados do contrato de execução
│   ├── mapping/adk.py           # mapper ADK -> contrato UI/API
│   ├── evaluation/runner.py     # avaliação determinística contínua
│   ├── observability/gcp.py     # logs/métricas JSON para Google Cloud
│   ├── policies/budget.py       # policy de orçamento para loops ADK
│   └── main.py                  # CLI smoke
├── tests/test_foundation.py
├── docs/architecture.md
└── .github/workflows/ci.yml
```

## Pré-requisitos

- Python `>=3.10,<3.14` para instalação declarada do projeto.
- `pip`.
- Chave `GOOGLE_API_KEY` ou configuração Vertex AI compatível com ADK.

A restrição `<3.14` evita instalar o ADK em versões de Python ainda não declaradas como suportadas pelo ecossistema atual.

## Setup local

```bash
cd adk-agent-orchestrator
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -c constraints-3.13.txt -e '.[dev]'
cp .env.example .env
```

Escolha o arquivo `constraints-3.10.txt`, `constraints-3.11.txt`,
`constraints-3.12.txt` ou `constraints-3.13.txt` conforme a versão do Python.
O runtime é certificado para `google-adk[mcp]==2.6.1`; uma versão diferente falha
explicitamente durante o bootstrap.

Edite `.env` e configure `GOOGLE_API_KEY` quando quiser executar uma chamada real ao modelo.

## Executar testes e checks

```bash
pytest -q
ruff check .
python -m compileall -q src tests
```

## Configuração de Tools e MCP

```bash
ADK_TOOL_TIMEOUT_SECONDS="10"
ADK_MCP_SERVERS='[{"name":"filesystem","transport":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","."]}]'
```

Consulte detalhes em [`docs/tools.md`](docs/tools.md).

## Avaliação e produção

```bash
python -m orchestrator.evaluation eval/datasets/phase5_smoke.json
```

Consulte [`docs/evaluation.md`](docs/evaluation.md), [`docs/observability.md`](docs/observability.md) e [`docs/runbooks/`](docs/runbooks/).

## Contrato de execução para UI/API

```bash
adk-orchestrator-smoke --contract-json "Validar contrato Fase 4"
```

A versão atual do contrato é `orchestrator.execution.v1` e inclui `task`, `subtasks`, `events`, `metrics`, `decision_metadata` e `artifacts`. Consulte [`docs/contracts/README.md`](docs/contracts/README.md) e o snapshot [`docs/contracts/execution_contract_v1.example.json`](docs/contracts/execution_contract_v1.example.json).

## Webapp React

A aplicação principal é a SPA React em [`webapp-react`](webapp-react), servida pelo FastAPI em `/` e `/app`. Ela oferece execução demo e real, respostas progressivas em Chat/DAG, verificação iterativa e controles event-driven (manual, webhook e agendamento).

Build do bundle React (obrigatório antes de iniciar o servidor):

```bash
cd webapp-react
npm ci
npm run build
```

Subir o servidor:

```bash
python run_server.py
```

Abra `http://localhost:5000` e use **Load Demo** para validar a interface sem uma chave de modelo.

Desenvolvimento isolado do painel:

```bash
cd webapp-react
npm run dev
```

O servidor Vite encaminha `/api` para `http://localhost:5000`, portanto mantenha também `python run_server.py` em execução durante o desenvolvimento.

O diretório [`webapp/ui`](webapp/ui) permanece como implementação anterior/especializada do Event Log e gera os artefatos em [`webapp/static`](webapp/static).

## Executar via CLI própria

```bash
adk-orchestrator-smoke "Validar workflows ADK da Fase 2"
```

## Executar via ADK CLI/Web

O ADK espera um módulo com `root_agent`. Este repositório disponibiliza `src/orchestrator/agent.py` para esse propósito.

```bash
adk run src/orchestrator
```

ou, para interface web de desenvolvimento:

```bash
adk web --port 8000
```

> `adk web` é recomendado apenas para desenvolvimento e depuração local.

## Próximos passos

1. Expor o contrato por uma API HTTP para Web/Android.
2. Adicionar datasets online com modelos reais em pipeline separado.
3. Persistir histórico de avaliações e métricas em BigQuery/Monitoring.
4. Ligar `BudgetPolicy` a callbacks/state avançados do ADK.
