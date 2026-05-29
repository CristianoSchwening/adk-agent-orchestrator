# adk-agent-orchestrator

Repositório **greenfield** para a reimplementação do orquestrador usando **Google Agent Development Kit (ADK) para Python**.

Esta entrega implementa a **Fase 2 — Workflows ADK Python** sobre a fundação ADK-only da Fase 1:

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
- Testes de smoke para configuração, tools, políticas e composição dos workflows.

> A implementação não reaproveita runtime legado (`Workforce`, `TaskBoard` ou `Subtask`). O novo desenho parte das primitivas oficiais do ADK Python.

## Arquitetura da Fase 2

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
        └── human_in_the_loop_workflow (ADK SequentialAgent + tool)
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

1. Ligar `BudgetPolicy` a callbacks/state avançados do ADK.
2. Criar adapter de eventos ADK para o contrato de UI.
3. Persistir sessões e artefatos fora de memória para ambientes compartilhados.
4. Adicionar observabilidade de produção e rastreamento de decisões human-in-the-loop.
