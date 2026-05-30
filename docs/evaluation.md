# Fase 5 — Avaliação contínua

A Fase 5 adiciona avaliação determinística e readiness de produção sem exigir
credenciais de modelo em CI.

## Critérios

Os datasets em `eval/datasets/` definem critérios por arquivo:

- `min_quality_score`: proporção mínima de casos que precisam passar.
- `min_safety_score`: proporção mínima de casos seguros.
- `max_estimated_cost_usd`: orçamento máximo estimado para o dataset.
- `max_latency_ms`: latência máxima permitida por caso.

## Dataset inicial

- `eval/datasets/phase5_smoke.json`: valida contrato `orchestrator.execution.v1`,
  capacidades de tools/MCP, workflows esperados e segurança de HITL.

## Execução local

```bash
python -m orchestrator.evaluation eval/datasets/phase5_smoke.json
```

A saída é JSON e retorna código de erro diferente de zero quando algum critério
falha.

## CI

O workflow `.github/workflows/evaluation.yml` roda:

```bash
pytest -q
ruff check .
python -m compileall -q src tests
python -m orchestrator.evaluation eval/datasets/phase5_smoke.json
```

## Referência do legado

O legado `meu-orquestrador` inspirou a estrutura objetivo → expectativa →
resultado consolidado dos datasets. A implementação nova continua ADK-only e
não importa `Workforce`, `TaskBoard`, `Subtask`, `Toolkit` ou integração Ollama.

## Próximas extensões

1. Adicionar datasets online com modelos reais em pipeline separado.
2. Armazenar resultados históricos em artifact ou BigQuery.
3. Criar benchmarks de regressão por workflow e tool.
4. Medir custo real por provedor/modelo quando callbacks de uso estiverem disponíveis.
