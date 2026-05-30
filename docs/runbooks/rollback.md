# Runbook — Rollback

## Cloud Run

1. Liste revisões:

```bash
gcloud run revisions list --service adk-agent-orchestrator --region REGION
```

2. Direcione tráfego para a última revisão saudável:

```bash
gcloud run services update-traffic adk-agent-orchestrator \
  --region REGION \
  --to-revisions REVISION=100
```

3. Valide:

```bash
python -m orchestrator.evaluation eval/datasets/phase5_smoke.json
```

## GKE

1. Verifique histórico:

```bash
kubectl rollout history deployment/adk-agent-orchestrator
```

2. Faça rollback:

```bash
kubectl rollout undo deployment/adk-agent-orchestrator
```

3. Monitore logs e métricas por pelo menos 30 minutos.

## Critérios de sucesso

- Avaliação determinística passa.
- Taxa de erro volta ao baseline.
- Latência p95 volta ao SLO.
- Contrato `orchestrator.execution.v1` permanece válido.
