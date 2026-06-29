# Design Document — rage-quota-management

## Visão Geral

O sistema de gerenciamento de cotas R.A.G.E. introduz uma camada de pré-roteamento no ADK Agent Orchestrator. Toda requisição é interceptada por um **Classificador R.A.G.E.** — um `LlmAgent` ADK dedicado — que avalia 4 eixos (Recência, Ação, Granularidade, Escopo), calcula o custo em cotas, seleciona o modelo LLM adequado e define a modalidade de execução (síncrona ou assíncrona) antes de delegar ao root agent. O design segue estritamente os padrões existentes do projeto: `agents/specialists.py` para o agente, `policies/budget.py` para policies, `contracts/dto.py` para DTOs, e `config.py` para settings.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     ADK Runner (bootstrap.py)                   │
│                                                                 │
│  User Request                                                   │
│       │                                                         │
│       ▼                                                         │
│  ┌────────────────────────┐                                     │
│  │  RageClassifierAgent   │  ← novo LlmAgent (pre-routing)      │
│  │  (agents/specialists)  │    avalia 4 eixos R.A.G.E.          │
│  │                        │    produz RageDecision              │
│  │  tools:                │    grava em session_state           │
│  │  - evaluate_rage_axes  │    ["rage_decision"]                │
│  │  - check_quota         │                                     │
│  └──────────┬─────────────┘                                     │
│             │ session_state["rage_decision"]                    │
│             ▼                                                   │
│  ┌────────────────────────┐                                     │
│  │   Root Orchestrator    │  ← root agent existente             │
│  │   Agent (root.py)      │    lê rage_decision do estado       │
│  │                        │    roteia para Batch API se async   │
│  └────────────────────────┘                                     │
│                                                                 │
│  QuotaStore (policies/quota.py)  ← lê QuotaConfig (YAML/JSON)  │
│       ├── in-memory counters per user                           │
│       └── debita após execução concluída                        │
└─────────────────────────────────────────────────────────────────┘
```

O `RageClassifierAgent` é posicionado como `sub_agent` do `SequentialAgent` que envolve o root agent, OU é inserido como primeiro sub-agente em uma sequência pré-routing. A abordagem mais compatível com o ADK é criar um `SequentialAgent` wrapper de pré-routing conforme descrito na seção de integração.

---

## Componentes e Arquivos

### Novos arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/orchestrator/agents/rage.py` | Fábrica do `RageClassifierAgent` e ferramenta `evaluate_rage_axes` |
| `src/orchestrator/policies/quota.py` | `QuotaPolicy`, `QuotaStore`, `QuotaConfig`, leitura YAML/JSON |
| `src/orchestrator/contracts/rage_dto.py` | `RageDecision`, `RageAxis`, `QuotaStatusDTO` |

### Arquivos modificados

| Arquivo | Modificação |
|---|---|
| `src/orchestrator/contracts/dto.py` | Adiciona campo `quota_status: QuotaStatusDTO \| None` ao `ExecutionContractDTO` |
| `src/orchestrator/config.py` | Adiciona campos `quota_config_dir`, `quota_default_limit`, `quota_async_discount_pct`, `quota_reset_day` ao `OrchestratorSettings` |
| `src/orchestrator/agents/root.py` | Embrulha o root agent em sequência pré-routing com o `RageClassifierAgent` |
| `src/orchestrator/mapping/adk.py` | Mapeia `rage_decision` e `quota_status` do estado de sessão para o contrato |
| `src/orchestrator/runner/bootstrap.py` | Adiciona `rage_decision` e `quota_status` ao `initial_session_state` |


---

## Modelos de Dados

### `contracts/rage_dto.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

RageExecutionMode = Literal["synchronous", "asynchronous"]
RageModel = Literal["haiku", "sonnet", "gpt-4o-mini", "gpt-4o", "default"]

@dataclass(frozen=True)
class RageAxis:
    """Resultado da avaliação de um único eixo R.A.G.E."""
    name: str                     # "R" | "A" | "G" | "E"
    label: str                    # ex: "Recência e Volume"
    cost: int                     # 0 ou 1 por eixo (ver tabela)
    rationale: str                # explicação textual

@dataclass(frozen=True)
class RageDecision:
    """Decisão imutável produzida pelo Classificador R.A.G.E."""
    axes: tuple[RageAxis, ...]        # exatamente 4 eixos
    total_cost: int                    # soma dos custos dos eixos (0–3+ cotas)
    selected_model: RageModel          # modelo LLM selecionado
    execution_mode: RageExecutionMode  # synchronous | asynchronous
    async_cost: int | None             # custo com desconto se async disponível
    is_urgent: bool                    # força síncrono se True
    classification_label: str          # "Busca Simples" | "Análise Investigativa" | etc.
    session_key: str = "rage_decision" # chave no estado de sessão ADK

@dataclass(frozen=True)
class QuotaStatusDTO:
    """Status de cotas para inclusão no ExecutionContractDTO."""
    consumed: int          # cotas consumidas no período corrente
    limit: int             # limite mensal configurado
    available: int         # limit - consumed
    next_reset_at: str     # ISO 8601 UTC do próximo reset
    user_id: str | None = None  # preenchido apenas para perfil admin
```

### Tabela de Decisão R.A.G.E. (custo em cotas)

| Classificação | R | A | G | E | Total |
|---|---|---|---|---|---|
| Busca Simples | 0 | 0 | 0 | 0 | **0** |
| Resumo de Contexto Base | 0 | 0 | 0 | 0 | **0** |
| Análise Investigativa Simples | 0–1 | 1 | 0 | 0 | **1** |
| Análise Comparativa / Frota | 0–1 | 1 | 1 | 0–1 | **1–2** |
| Análise de Causa Raiz (RCA) | 1 | 1 | 1 | 1 | **3+** |

### `policies/quota.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json, yaml
from datetime import datetime, timezone
from orchestrator.contracts.rage_dto import QuotaStatusDTO, RageDecision

@dataclass
class QuotaConfig:
    """Configuração de cotas por usuário lida de arquivo YAML ou JSON."""
    user_id: str
    monthly_limit: int

@dataclass
class QuotaStore:
    """Mantém contadores in-memory e lê QuotaConfig de arquivos por usuário."""
    config_dir: Path
    default_limit: int
    reset_day: int
    _counters: dict[str, int] = field(default_factory=dict, init=False)

    def load_config(self, user_id: str) -> QuotaConfig: ...
    def get_status(self, user_id: str) -> QuotaStatusDTO: ...
    def can_authorize(self, user_id: str, cost: int) -> bool: ...
    def debit(self, user_id: str, cost: int) -> None: ...
    def _next_reset_at(self) -> str: ...
```


---

## Interfaces e Contratos de Integração

### `OrchestratorSettings` — novos campos

```python
# config.py — adicionados ao dataclass OrchestratorSettings
quota_config_dir: str = "quota_configs"          # ADK_QUOTA_CONFIG_DIR
quota_default_limit: int = 20                     # ADK_QUOTA_DEFAULT_LIMIT
quota_async_discount_pct: int = 40               # ADK_QUOTA_ASYNC_DISCOUNT_PCT (30–50)
quota_reset_day: int = 1                          # ADK_QUOTA_RESET_DAY (1–28)
```

Validações em `__post_init__` ou parsers dedicados:
- `quota_async_discount_pct` fora de `[30, 50]` → `ValueError("ADK_QUOTA_ASYNC_DISCOUNT_PCT must be between 30 and 50.")`
- `quota_reset_day` fora de `[1, 28]` → `ValueError("ADK_QUOTA_RESET_DAY must be between 1 and 28.")`

### `ExecutionContractDTO` — novo campo

```python
# contracts/dto.py — adicionado ao dataclass ExecutionContractDTO
quota_status: QuotaStatusDTO | None = None
```

O campo é opcional para retrocompatibilidade com testes existentes. Após ativação da feature, o mapper sempre o preenche.

### Estado de sessão ADK — novas chaves

| Chave | Tipo | Responsável por escrever |
|---|---|---|
| `rage_decision` | `dict` (serialização de `RageDecision`) | `RageClassifierAgent` |
| `quota_status` | `dict` (serialização de `QuotaStatusDTO`) | `QuotaStore` via mapper |
| `rage_fallback_active` | `bool` | `QuotaStore` quando cotas esgotadas |

### Integração do `RageClassifierAgent` com Root Agent

A integração usa um `SequentialAgent` de pré-routing no `create_root_agent`:

```python
# agents/root.py — estrutura proposta
from orchestrator.agents.rage import create_rage_classifier_agent

def create_root_agent(settings: OrchestratorSettings | None = None) -> Any:
    resolved_settings = settings or OrchestratorSettings.from_env()
    SequentialAgent = load_symbol("google.adk.agents.sequential_agent", "SequentialAgent")
    rage_agent = create_rage_classifier_agent(resolved_settings)
    root = _create_root_llm_agent(resolved_settings)           # lógica atual extraída
    return SequentialAgent(
        name="rage_preflight_root_agent",
        description="Pre-routing R.A.G.E. classification + root orchestration.",
        sub_agents=[rage_agent, root],
    )
```

O `RageClassifierAgent` grava `rage_decision` no estado de sessão; o root agent o lê via instrução de sistema.

---

## Ferramenta `evaluate_rage_axes`

Ferramenta local Python (não LLM) usada pelo `RageClassifierAgent` para avaliar os 4 eixos deterministicamente a partir de metadados da requisição. Evita que a lógica de classificação seja não-determinística quando os sinais são objetivos (ex: presença de manuais PDF no contexto).

```python
# agents/rage.py
def evaluate_rage_axes(
    *,
    has_long_term_history: bool,
    action_type: str,            # "list" | "filter" | "diagnose" | "rca" | ...
    asset_count: int,            # 1 = pontual, 2+ = comparativa/frota
    context_sources: list[str],  # ["vibration", "temperature", "pdf", "cmms", "erp"]
    is_urgent: bool,
    user_id: str,
) -> dict:
    """Avalia os 4 eixos e retorna serialização de RageDecision."""
    ...
```

A ferramenta também consulta o `QuotaStore` (injeção via closure no momento da criação do agente) para verificar disponibilidade de cotas e inclui o `QuotaStatus` no resultado.

---

## Fluxo de Execução Detalhado

### Caso 1 — Análise RCA (custo 3 cotas, sem urgência)

```
1. Request chega ao SequentialAgent pré-routing
2. RageClassifierAgent avalia: R=1, A=1, G=1, E=1 → total=3, mode=async sugerido
3. RageClassifierAgent verifica QuotaStore: consumed=17, limit=20 → disponível=3 ✓
4. RageClassifierAgent responde ao usuário:
   "Esta análise consumirá 3 Cotas de Uso no modo síncrono,
    ou 2 Cotas de Uso no modo assíncrono (resultado em até 12h).
    Qual modalidade prefere?"
5. rage_decision gravado no estado de sessão
6. Root agent recebe control com rage_decision disponível
7. Se async confirmado: Root encaminha ao Batch API (OpenAI/Anthropic)
8. ExecutionContractDTO retornado com task.status="pending" e quota_status preenchido
```

### Caso 2 — Urgência operacional ("máquina parada")

```
1. RageClassifierAgent detecta "máquina parada" no texto → is_urgent=True
2. Força execution_mode=synchronous independente do custo
3. Não oferece opção assíncrona
4. Prossegue imediatamente para o root agent
```

### Caso 3 — Cota esgotada

```
1. RageClassifierAgent avalia custo=1, consumed=20, limit=20 → insuficiente
2. QuotaStore retorna can_authorize=False, não debita
3. rage_fallback_active=True gravado no estado de sessão
4. Root agent recebe instrução de fallback: consultar banco de dados padrão sem LLM avançado
5. ExecutionContractDTO retornado com:
   - events: [EventDTO(severity="warning", message="Cotas de Uso esgotadas...")]
   - quota_status: QuotaStatusDTO(available=0, next_reset_at="...")
```

---

## Tratamento de Erros

| Situação | Comportamento |
|---|---|
| Arquivo `QuotaConfig` não encontrado | Aplicar `quota_default_limit` do `OrchestratorSettings` |
| `ADK_QUOTA_ASYNC_DISCOUNT_PCT` fora de 30–50 | `ValueError` no startup |
| `ADK_QUOTA_RESET_DAY` fora de 1–28 | `ValueError` no startup |
| `evaluate_rage_axes` lança exceção | Log de erro + fallback para `RageDecision` com custo=0 e mode=synchronous |
| Batch API retorna erro | `task.status="failed"` + evento de error no contrato |
| YAML/JSON malformado no `QuotaConfig` | Log de warning + aplicar `quota_default_limit` |


---

## Invalidação de Cache do `QuotaStore`

O `QuotaStore` mantém contadores in-memory. Eventos que podem exigir reavaliação do contexto de cotas (sem debitar/resetar contadores, mas sinalizando ao `RageClassifierAgent` para reclassificar):

- Novos alarmes recebidos
- Novas OS/CMMS registradas
- Novas medições com desvio detectado
- Atualizações de manuais PDF

Esses eventos são comunicados via um método `invalidate_context_cache(user_id: str)` no `QuotaStore` que força o `RageClassifierAgent` a reclassificar na próxima requisição sem alterar o contador de cotas.

---

## Mapeamento no `mapping/adk.py`

Novas chaves adicionadas ao `WORKFLOW_STATE_KEYS`:

```python
WORKFLOW_STATE_KEYS = {
    ...existing keys...
    "rage_decision": ("rage_classifier", "classify"),
    "quota_status": ("rage_classifier", "quota"),
}
```

A função `map_adk_execution` é atualizada para extrair `rage_decision` e `quota_status` do estado de sessão e preencher `ExecutionContractDTO.quota_status`.

---

## Batch API — Integração Assíncrona

Quando `execution_mode == "asynchronous"`, o root agent usa a instrução recebida via `rage_decision` para encaminhar ao endpoint correto:

| Modelo selecionado | Batch API |
|---|---|
| `sonnet` | Anthropic Batch API (`/v1/messages/batches`) |
| `gpt-4o` | OpenAI Batch API (`/v1/batches`) |
| `haiku` | Anthropic Batch API |
| `gpt-4o-mini` | OpenAI Batch API |

O resultado é tratado como tarefa assíncrona: `task.status="pending"` até conclusão. O polling/webhook é responsabilidade de uma fase futura (fora do escopo deste design).

---

## Segurança e Privacidade

- Arquivos `QuotaConfig` nunca são logados com conteúdo — apenas o `user_id` e `limit` são referenciados em logs de info.
- O campo `user_id` no `QuotaStatusDTO` é preenchido **apenas** quando o perfil do usuário é admin, evitando exposição em contratos de usuários comuns.
- Contadores in-memory são isolados por `user_id` — não há vazamento entre usuários.
- O `QuotaStore` não armazena tokens nem créditos de IA — apenas unidades abstratas de "Cotas de Uso".


---

## Correctness Properties

*Uma property é uma característica ou comportamento que deve ser verdadeiro em todas as execuções válidas do sistema — essencialmente, uma declaração formal sobre o que o sistema deve fazer. As properties servem de ponte entre especificações legíveis por humanos e garantias verificáveis automaticamente.*

### Property 1: Classificação de eixo é determinística e consistente com a tabela de decisão

*Para qualquer* combinação dos 4 eixos R.A.G.E. (has_long_term_history, action_type, asset_count, context_sources), o custo total calculado pelo `evaluate_rage_axes` deve ser consistente com a tabela de decisão e permanecer idêntico em múltiplas invocações com os mesmos inputs.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.6**

---

### Property 2: RageDecision é sempre completa e imutável

*Para qualquer* input válido, a `RageDecision` produzida deve conter exatamente 4 `RageAxis` com nome, label, custo e rationale preenchidos, além de `total_cost`, `selected_model`, `execution_mode`, `is_urgent` e `classification_label`. Tentativas de mutação devem lançar `FrozenInstanceError`.

**Validates: Requirements 1.5, 2.4**

---

### Property 3: Desconto assíncrono respeita o intervalo configurado

*Para qualquer* `RageDecision` com `total_cost >= 2` e `quota_async_discount_pct` em [30, 50], o `async_cost` deve satisfazer `total_cost * 0.50 <= async_cost <= total_cost * 0.70` (ou seja, desconto entre 30% e 50%).

**Validates: Requirements 5.1**

---

### Property 4: Urgência operacional força modalidade síncrona

*Para qualquer* requisição cujo texto contenha expressão de urgência operacional reconhecida (incluindo "máquina parada" e "alarme crítico"), `RageDecision.execution_mode` deve ser `"synchronous"` e `RageDecision.is_urgent` deve ser `True`, independentemente do `total_cost`.

**Validates: Requirements 5.2, 5.3**

---

### Property 5: QuotaConfig round-trip preserva o limite configurado

*Para qualquer* valor inteiro positivo de `monthly_limit`, escrever uma `QuotaConfig` em arquivo YAML ou JSON e lê-la de volta com o `QuotaStore` deve retornar o mesmo `monthly_limit`.

**Validates: Requirements 3.1**

---

### Property 6: Autorização de cotas é consistente com a aritmética de consumo

*Para qualquer* par `(consumed, limit)` no estado do `QuotaStore` e qualquer `cost >= 0`, `can_authorize` deve retornar `True` se e somente se `consumed + cost <= limit`.

**Validates: Requirements 3.4, 3.5**

---

### Property 7: Débito de cotas preserva a invariante de contagem

*Para qualquer* sequência de operações `debit(cost_i)` todas autorizadas, o `consumed` final deve ser igual à soma de todos os `cost_i` debitados.

**Validates: Requirements 3.2, 3.6**

---

### Property 8: Rejeição por cota esgotada não altera o contador

*Para qualquer* estado em que `consumed + cost > limit`, chamar `debit` deve ser impedido pelo `QuotaStore` (cota insuficiente retornada antes do débito) e `consumed` deve permanecer inalterado após a tentativa.

**Validates: Requirements 3.5**

---

### Property 9: Usuário sem arquivo de configuração recebe o limite padrão

*Para qualquer* `user_id` que não possui arquivo `QuotaConfig` no `config_dir`, `QuotaStore.get_status(user_id).limit` deve ser igual a `OrchestratorSettings.quota_default_limit`.

**Validates: Requirements 3.3**

---

### Property 10: Fallback por cota esgotada gera evento de warning e aviso no contrato

*Para qualquer* execução em que o usuário não possui cotas suficientes, o `ExecutionContractDTO` resultante deve conter pelo menos um `EventDTO` com `severity="warning"` e o `quota_status` deve ter `available=0` com `next_reset_at` preenchido.

**Validates: Requirements 6.2, 6.3**

---

### Property 11: quota_status sempre presente e consistente pós-execução

*Para qualquer* execução concluída com sucesso, `ExecutionContractDTO.quota_status` não deve ser `None` e deve satisfazer `quota_status.available == quota_status.limit - quota_status.consumed`, com `consumed` refletindo o custo debitado da `RageDecision`.

**Validates: Requirements 7.1, 7.2, 7.3**

---

### Property 12: OrchestratorSettings lê e valida variáveis de quota de ambiente

*Para qualquer* valor de `ADK_QUOTA_CONFIG_DIR`, `ADK_QUOTA_DEFAULT_LIMIT` e `ADK_QUOTA_RESET_DAY` (em range válido), `OrchestratorSettings.from_env()` deve refletir esses valores. Para `ADK_QUOTA_ASYNC_DISCOUNT_PCT` fora do intervalo [30, 50], deve lançar `ValueError`.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

---

### Property 13: RageDecision é persistida no estado de sessão ADK

*Para qualquer* requisição processada pelo `RageClassifierAgent`, o estado de sessão ADK deve conter a chave `"rage_decision"` com um dicionário serializável representando a `RageDecision` após a execução do agente.

**Validates: Requirements 2.3, 2.4**

