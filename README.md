# adk-agent-orchestrator

Repositório **greenfield** para a reimplementação do orquestrador usando **Google Agent Development Kit (ADK) para Python**.

Esta entrega implementa a **Fase 1 — Fundação ADK**:

- `RootOrchestratorAgent` em ADK Python.
- `Runner` oficial do ADK.
- `InMemorySessionService` para sessões locais.
- `InMemoryArtifactService` para artefatos locais.
- Configuração por `.env`/variáveis de ambiente.
- Testes de smoke para configuração, tools e políticas iniciais.
- Estrutura de repositório pronta para evoluir para workflows multiagente.

> A fundação não reaproveita o runtime legado (`Workforce`, `TaskBoard` ou `Subtask`). O novo desenho parte das primitivas do ADK.

## Arquitetura da Fase 1

```text
User / CLI / ADK Web
        │
        ▼
RootOrchestratorAgent (ADK Agent)
        │
        ├── capture_objective tool
        ├── get_orchestrator_status tool
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
│   ├── runner/bootstrap.py      # Runner + SessionService + ArtifactService
│   ├── tools/foundation.py      # tools mínimas da Fase 1
│   ├── policies/budget.py       # policy base para próximas fases
│   └── main.py                  # CLI smoke
├── tests/test_foundation.py
├── docs/architecture.md
└── .github/workflows/ci.yml
```

## Pré-requisitos

- Python `>=3.10,<3.14`.
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

## Executar testes

```bash
pytest -q
```

## Executar via CLI própria

```bash
adk-orchestrator-smoke "Validar fundação ADK da Fase 1"
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

1. Implementar `SequentialAgent` para pipeline Planner → Executor → Critic → Summarizer.
2. Implementar `ParallelAgent` para agentes especialistas independentes.
3. Implementar `LoopAgent` para review-critic e refinamento iterativo.
4. Ligar `BudgetPolicy` a callbacks/state do ADK.
5. Criar adapter de eventos ADK para o contrato de UI.
