# Observabilidade e Google Cloud readiness

A Fase 5 introduz helpers de observabilidade em `src/orchestrator/observability/`.
Eles emitem JSON estruturado compatível com Cloud Run/GKE/Cloud Logging sem
adicionar dependências obrigatórias de Google Cloud.

## Variáveis

| Variável | Uso |
| --- | --- |
| `ADK_ENVIRONMENT` | Ambiente lógico (`local`, `staging`, `prod`). |
| `ADK_LOG_LEVEL` | Nível de log (`INFO`, `DEBUG`, `WARNING`, `ERROR`). |
| `GOOGLE_CLOUD_PROJECT` / `GCP_PROJECT` | Projeto GCP para enriquecer logs. |
| `K_SERVICE` | Nome do serviço Cloud Run quando disponível. |

## Logs estruturados

```python
from orchestrator.observability import get_logger

logger = get_logger("orchestrator.runner")
logger.info("execution completed", extra={"json_fields": {"task_id": "task-1"}})
```

## Métricas

```python
from orchestrator.observability import emit_metric

emit_metric("evaluation_passed", 1, labels={"dataset": "phase5_smoke"})
```

O helper emite uma entrada JSON com `metric_type` no namespace
`custom.googleapis.com/adk_agent_orchestrator/`. Em produção, esse payload pode
ser roteado para Cloud Monitoring via log-based metrics ou substituído por um
cliente oficial.

## Readiness de produção

- Usar Secret Manager para chaves de modelo e endpoints MCP.
- Executar em Cloud Run ou GKE com service account mínima.
- Ativar Cloud Logging, Error Reporting, Cloud Trace e métricas baseadas em log.
- Publicar resultados de avaliação como artifacts de CI.
- Configurar alertas para erro de contrato, aumento de latência, falha de HITL e
  regressão de dataset.
