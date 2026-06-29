# Implementation Plan: rage-quota-management

## Overview

Implementação do sistema de gerenciamento de cotas R.A.G.E. no ADK Agent Orchestrator em Python. A feature introduz três novos arquivos (`contracts/rage_dto.py`, `policies/quota.py`, `agents/rage.py`), modifica quatro arquivos existentes (`contracts/dto.py`, `config.py`, `agents/root.py`, `mapping/adk.py`) e adiciona state inicial no `runner/bootstrap.py`. O Classificador R.A.G.E. é posicionado como pré-roteador via `SequentialAgent` antes do root agent existente.

---

## Tasks

- [ ] 1. Criar DTOs R.A.G.E. em `contracts/rage_dto.py`
  - [ ] 1.1 Implementar `RageAxis`, `RageDecision` e `QuotaStatusDTO` como dataclasses `frozen=True`
    - Criar `src/orchestrator/contracts/rage_dto.py` com os tipos `RageExecutionMode`, `RageModel`, `RageAxis`, `RageDecision` e `QuotaStatusDTO` seguindo o padrão de `contracts/dto.py`
    - `RageDecision.axes` deve ser `tuple[RageAxis, ...]` com exatamente 4 elementos
    - `QuotaStatusDTO` deve conter `consumed`, `limit`, `available`, `next_reset_at` e `user_id: str | None`
    - Exportar os novos tipos em `src/orchestrator/contracts/__init__.py`
    - _Requirements: 1.5, 7.2, 7.5_

  - [ ]* 1.2 Escrever property test para imutabilidade de `RageDecision`
    - **Property 2: RageDecision é sempre completa e imutável**
    - Gerar inputs válidos via Hypothesis e verificar que toda `RageDecision` construída tem exatamente 4 eixos e levanta `FrozenInstanceError` em tentativas de mutação
    - **Validates: Requirements 1.5, 2.4**

- [ ] 2. Adicionar campos de quota ao `OrchestratorSettings` em `config.py`
  - [ ] 2.1 Adicionar `quota_config_dir`, `quota_default_limit`, `quota_async_discount_pct` e `quota_reset_day` ao dataclass `OrchestratorSettings`
    - Adicionar os quatro campos com valores padrão: `quota_config_dir="quota_configs"`, `quota_default_limit=20`, `quota_async_discount_pct=40`, `quota_reset_day=1`
    - Implementar parsers `_parse_quota_discount_pct` e `_parse_quota_reset_day` com validação de intervalo
    - `quota_async_discount_pct` fora de [30, 50] → `ValueError("ADK_QUOTA_ASYNC_DISCOUNT_PCT must be between 30 and 50.")`
    - `quota_reset_day` fora de [1, 28] → `ValueError("ADK_QUOTA_RESET_DAY must be between 1 and 28.")`
    - Atualizar `from_env()` para ler `ADK_QUOTA_CONFIG_DIR`, `ADK_QUOTA_DEFAULT_LIMIT`, `ADK_QUOTA_ASYNC_DISCOUNT_PCT`, `ADK_QUOTA_RESET_DAY`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 2.2 Escrever property test para leitura e validação das variáveis de ambiente de quota
    - **Property 12: OrchestratorSettings lê e valida variáveis de quota de ambiente**
    - Usar Hypothesis para gerar combinações válidas de variáveis de ambiente e verificar que os valores são refletidos; gerar `discount_pct` fora de [30, 50] e verificar `ValueError`
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

- [ ] 3. Implementar `QuotaStore` em `policies/quota.py`
  - [ ] 3.1 Implementar `QuotaConfig` e `QuotaStore` com leitura YAML/JSON e contadores in-memory
    - Criar `src/orchestrator/policies/quota.py` com `QuotaConfig` e `QuotaStore`
    - `QuotaStore.load_config(user_id)` deve tentar ler `{config_dir}/{user_id}.yaml` e depois `{user_id}.json`; aplicar `default_limit` quando o arquivo não é encontrado; log warning para YAML/JSON malformado e aplicar `default_limit`
    - `QuotaStore.get_status(user_id)` retorna `QuotaStatusDTO` com `consumed`, `limit`, `available` e `next_reset_at` calculado via `_next_reset_at()`
    - `QuotaStore.can_authorize(user_id, cost)` retorna `True` se e somente se `consumed + cost <= limit`
    - `QuotaStore.debit(user_id, cost)` incrementa o contador in-memory somente após autorização (não deve debitar se `can_authorize` retornar `False`)
    - `QuotaStore.invalidate_context_cache(user_id)` sinaliza reclassificação sem alterar contador
    - `_next_reset_at()` calcula próximo reset baseado em `reset_day` e UTC atual
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 3.2 Escrever property test para round-trip de `QuotaConfig`
    - **Property 5: QuotaConfig round-trip preserva o limite configurado**
    - Usar Hypothesis para gerar `monthly_limit` inteiros positivos, escrever arquivo YAML e JSON temporários e verificar que `QuotaStore.load_config` retorna o mesmo limite
    - **Validates: Requirements 3.1**

  - [ ]* 3.3 Escrever property test para aritmética de autorização de cotas
    - **Property 6: Autorização de cotas é consistente com a aritmética de consumo**
    - Usar Hypothesis para gerar pares `(consumed, limit, cost)` e verificar que `can_authorize` retorna `True` sse `consumed + cost <= limit`
    - **Validates: Requirements 3.4, 3.5**

  - [ ]* 3.4 Escrever property test para invariante de débito sequencial
    - **Property 7: Débito de cotas preserva a invariante de contagem**
    - Gerar sequências de operações `debit(cost_i)` autorizadas e verificar que `consumed` final é igual à soma dos custos debitados
    - **Validates: Requirements 3.2, 3.6**

  - [ ]* 3.5 Escrever property test para rejeição sem alterar contador
    - **Property 8: Rejeição por cota esgotada não altera o contador**
    - Para estados em que `consumed + cost > limit`, verificar que `consumed` permanece inalterado após tentativa de débito negada
    - **Validates: Requirements 3.5**

  - [ ]* 3.6 Escrever property test para usuário sem arquivo recebe limite padrão
    - **Property 9: Usuário sem arquivo de configuração recebe o limite padrão**
    - Usar user_ids inexistentes no `config_dir` e verificar `get_status(user_id).limit == default_limit`
    - **Validates: Requirements 3.3**

- [ ] 4. Checkpoint — Garantir que DTOs, settings e QuotaStore passam em todos os testes
  - Garantir que todos os testes passam, perguntar ao usuário se surgirem dúvidas.

- [ ] 5. Implementar ferramenta `evaluate_rage_axes` e `RageClassifierAgent` em `agents/rage.py`
  - [ ] 5.1 Implementar a função `evaluate_rage_axes` como ferramenta local determinística
    - Criar `src/orchestrator/agents/rage.py`
    - Implementar `evaluate_rage_axes(*, has_long_term_history, action_type, asset_count, context_sources, is_urgent, user_id)` seguindo a tabela de decisão R.A.G.E.
    - Eixo R: custo=1 se `has_long_term_history=True`, senão 0
    - Eixo A: custo=1 e seleciona modelo avançado (sonnet/gpt-4o) se `action_type` in `{"diagnose", "rca", "compare"}`, senão 0
    - Eixo G: custo=1 se `asset_count >= 2`, senão 0
    - Eixo E: custo=1 (premium) se `context_sources` contém "pdf", "cmms" ou "erp", senão 0
    - Detectar urgência via `is_urgent` ou via presença de "máquina parada" / "alarme crítico" no `action_type` ou via flag externa
    - Calcular `total_cost`, `async_cost` (aplicando `quota_async_discount_pct`), `selected_model`, `execution_mode` e `classification_label`
    - Retornar serialização de `RageDecision` como `dict`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3_

  - [ ]* 5.2 Escrever property test para determinismo da classificação de eixos
    - **Property 1: Classificação de eixo é determinística e consistente com a tabela de decisão**
    - Usar Hypothesis para gerar combinações dos 4 eixos e verificar que o `total_cost` é idêntico em múltiplas invocações e consistente com a tabela de decisão
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.6**

  - [ ]* 5.3 Escrever property test para desconto assíncrono
    - **Property 3: Desconto assíncrono respeita o intervalo configurado**
    - Para `total_cost >= 2` e `discount_pct` em [30, 50], verificar que `async_cost` satisfaz `total_cost * 0.50 <= async_cost <= total_cost * 0.70`
    - **Validates: Requirements 5.1**

  - [ ]* 5.4 Escrever property test para urgência operacional força modo síncrono
    - **Property 4: Urgência operacional força modalidade síncrona**
    - Para qualquer input com `is_urgent=True` ou expressão de urgência reconhecida, verificar `execution_mode == "synchronous"` e `is_urgent == True`
    - **Validates: Requirements 5.2, 5.3**

  - [ ] 5.5 Implementar `create_rage_classifier_agent` como fábrica de `LlmAgent` ADK
    - Implementar `create_rage_classifier_agent(settings: OrchestratorSettings, quota_store: QuotaStore) -> Any` em `agents/rage.py` seguindo o padrão de `agents/specialists.py`
    - O agente recebe `evaluate_rage_axes` (com `quota_store` injetado via closure) como tool
    - Instrução do sistema deve orientar o agente a: avaliar 4 eixos, gravar `rage_decision` em `output_key="rage_decision"`, informar o usuário sobre custo antes de prosseguir (Req 4.1), oferecer opção async quando `total_cost >= 2` e sem urgência (Req 4.3), usar somente o termo "Cotas de Uso" (Req 4.2)
    - Instrução deve descrever o comportamento de fallback quando `rage_fallback_active=True`
    - Usar `output_key="rage_decision"` para gravação automática no estado de sessão ADK
    - _Requirements: 2.1, 2.2, 2.4, 4.1, 4.2, 4.3, 4.4_

- [ ] 6. Adicionar campo `quota_status` ao `ExecutionContractDTO` em `contracts/dto.py`
  - [ ] 6.1 Adicionar campo opcional `quota_status: QuotaStatusDTO | None = None` ao `ExecutionContractDTO`
    - Importar `QuotaStatusDTO` de `contracts/rage_dto.py`
    - Manter retrocompatibilidade: campo opcional com padrão `None`
    - _Requirements: 7.1, 7.5_

- [ ] 7. Integrar `RageClassifierAgent` com o Root Agent em `agents/root.py`
  - [ ] 7.1 Embrulhar root agent em `SequentialAgent` pré-routing com `RageClassifierAgent`
    - Extrair a lógica atual de criação do `LlmAgent` para uma função auxiliar `_create_root_llm_agent`
    - Criar `QuotaStore` a partir das `settings` dentro de `create_root_agent`
    - Instanciar `create_rage_classifier_agent(settings, quota_store)`
    - Retornar `SequentialAgent(name="rage_preflight_root_agent", sub_agents=[rage_agent, root])` usando `load_symbol("google.adk.agents.sequential_agent", "SequentialAgent")`
    - Atualizar `ROOT_AGENT_INSTRUCTION` para mencionar leitura de `rage_decision` do estado de sessão e comportamento de fallback
    - _Requirements: 2.2, 2.3, 5.4, 6.1_

- [ ] 8. Atualizar `mapping/adk.py` para mapear `rage_decision` e `quota_status`
  - [ ] 8.1 Adicionar chaves R.A.G.E. ao `WORKFLOW_STATE_KEYS` e preencher `quota_status` no contrato
    - Adicionar `"rage_decision": ("rage_classifier", "classify")` e `"quota_status": ("rage_classifier", "quota")` ao dicionário `WORKFLOW_STATE_KEYS`
    - Atualizar `map_adk_execution` para extrair `quota_status` do `state` e construir `QuotaStatusDTO` a partir do dict serializado
    - Passar `quota_status` ao `ExecutionContractDTO` no retorno de `map_adk_execution`
    - Para o caso de fallback (`rage_fallback_active=True`), incluir `EventDTO(severity="warning", message="Cotas de Uso esgotadas...")` na lista de `event_dtos`
    - _Requirements: 6.2, 6.3, 7.1, 7.3_

  - [ ]* 8.2 Escrever property test para `quota_status` sempre presente e consistente pós-execução
    - **Property 11: quota_status sempre presente e consistente pós-execução**
    - Simular execução concluída e verificar que `quota_status` não é `None` e que `available == limit - consumed`
    - **Validates: Requirements 7.1, 7.2, 7.3**

  - [ ]* 8.3 Escrever property test para fallback por cota esgotada gera evento de warning
    - **Property 10: Fallback por cota esgotada gera evento de warning e aviso no contrato**
    - Simular execução com `rage_fallback_active=True` e verificar presença de `EventDTO(severity="warning")` e `quota_status.available == 0` com `next_reset_at` preenchido
    - **Validates: Requirements 6.2, 6.3**

- [ ] 9. Atualizar `runner/bootstrap.py` para incluir estado inicial de quota
  - [ ] 9.1 Adicionar chaves `rage_decision` e `quota_status` ao `initial_session_state`
    - Atualizar `initial_session_state(settings)` para incluir `"rage_decision": None` e `"quota_status": None`
    - _Requirements: 2.3_

  - [ ]* 9.2 Escrever property test para persistência de `RageDecision` no estado de sessão ADK
    - **Property 13: RageDecision é persistida no estado de sessão ADK**
    - Verificar que após a execução do `RageClassifierAgent` o estado de sessão contém a chave `"rage_decision"` com um dicionário serializável
    - **Validates: Requirements 2.3, 2.4**

- [ ] 10. Checkpoint Final — Garantir que todos os testes passam
  - Garantir que todos os testes unitários e property tests passam, perguntar ao usuário se surgirem dúvidas.

---

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para MVP mais rápido
- Cada task referencia requisitos específicos para rastreabilidade
- Os property tests usam a biblioteca `hypothesis` (já disponível ou a instalar via `pyproject.toml`)
- O `QuotaStore` usa contadores in-memory por processo; sem persistência entre reinicializações — comportamento intencional conforme design
- O campo `user_id` em `QuotaStatusDTO` só é preenchido para perfil admin (verificar contexto de execução)
- A integração com Batch API (OpenAI/OpenAI) para modo assíncrono está fora do escopo desta implementação conforme design

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6"] },
    { "id": 4, "tasks": ["5.1", "6.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 6, "tasks": ["5.5"] },
    { "id": 7, "tasks": ["7.1"] },
    { "id": 8, "tasks": ["8.1", "9.1"] },
    { "id": 9, "tasks": ["8.2", "8.3", "9.2"] }
  ]
}
```
