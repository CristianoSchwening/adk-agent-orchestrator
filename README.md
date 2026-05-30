# adk-agent-orchestrator

Repositório **greenfield** para a reimplementação do orquestrador usando **Google Agent Development Kit (ADK) para Python**.

Esta entrega implementa a **Fase 4 — Contrato e UI** sobre Tools/MCP da Fase 3:

- `RootOrchestratorAgent` em ADK Python com subagentes de workflow.
- `Runner` oficial do ADK.
- `InMemorySessionService` para sessões locais.
- `InMemoryArtifactService` para artefatos locais.
- Configuração por `.env`/variáveis de ambiente.
- Workflows equivalentes usando apenas primitivas ADK Python:
  - `SequentialAgent` para pipeline Planner → Executor → Critic → Summarizer.
  - `ParallelAgent` para especialistas independentes.
  - `LoopAgent` para `review_critic`.
  - `LoopAgent` para `iterative_refinement`.
  - `SequentialAgent` com tool ADK para `human_in_the_loop`.
- Tools locais seguras para filesystem, HTTP, documentos, dados e planejamento de modelo.
- Catálogo de tools consultável pelo agente raiz.
- Factory lazy para integração externa via ADK `MCPToolset`.
- Timeouts, erros padronizados e métricas locais de uso de tools.
- Contrato JSON versionado `orchestrator.execution.v1` para UI/API.
- DTOs para task, subtasks, events, metrics, decision_metadata e artifacts.
- Mapper de ADK Session/Events/Artifacts para contrato de execução.
- Snapshot JSON em `docs/contracts/` para consumidores Web/Android/API.
- Testes de smoke para configuração, tools, contrato, políticas e composição dos workflows.

> A implementação não reaproveita runtime legado (`Workforce`, `TaskBoard` ou `Subtask`). O novo desenho parte das primitivas oficiais do ADK Python.

## Arquitetura da Fase 4

```text
User / CLI / ADK Web
        │
        ▼
RootOrchestratorAgent (ADK LlmAgent)
        │
        ├── capture_objective tool
        ├── get_orchestrator_status tool
        ├── sequential_workflow (ADK SequentialAgent)
        ├── parallel_workflow (ADK ParallelAgent)
        ├── review_critic_workflow (ADK LoopAgent)
        ├── iterative_refinement_workflow (ADK LoopAgent)
        ├── human_in_the_loop_workflow (ADK SequentialAgent + tool)
        ├── Phase 3 local tools + MCP toolsets
        └── Phase 4 execution contract mapper
        │
        ▼
ADK Runner
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
│   ├── agents/workflows.py      # factories dos workflows ADK da Fase 2
│   ├── runner/bootstrap.py      # Runner + SessionService + ArtifactService
│   ├── tools/foundation.py      # tools de status/captura
│   ├── tools/human.py           # tool de aprovação humana
│   ├── tools/local.py           # tools locais da Fase 3
│   ├── tools/catalog.py         # catálogo de tools
│   ├── tools/metrics.py         # métricas de uso de tools
│   ├── mcp/factory.py           # factory lazy para MCPToolset
│   ├── contracts/dto.py         # DTOs versionados do contrato de execução
│   ├── mapping/adk.py           # mapper ADK -> contrato UI/API
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
python -m pip install -e '.[dev]'
cp .env.example .env
```

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

## Contrato de execução para UI/API

```bash
adk-orchestrator-smoke --contract-json "Validar contrato Fase 4"
```

A versão atual do contrato é `orchestrator.execution.v1` e inclui `task`, `subtasks`, `events`, `metrics`, `decision_metadata` e `artifacts`. Consulte [`docs/contracts/README.md`](docs/contracts/README.md) e o snapshot [`docs/contracts/execution_contract_v1.example.json`](docs/contracts/execution_contract_v1.example.json).

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
2. Ligar métricas locais de tools a ADK Session Events e observabilidade de produção.
3. Ligar `BudgetPolicy` a callbacks/state avançados do ADK.
4. Persistir sessões e artefatos fora de memória para ambientes compartilhados.
