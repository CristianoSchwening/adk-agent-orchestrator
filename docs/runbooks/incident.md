# Runbook — Incidente de produção

## Sinais

- Aumento de `error_count` no contrato `orchestrator.execution.v1`.
- Falhas em `phase5_smoke` ou datasets online.
- Timeouts de tools/MCP acima do budget.
- Ausência de resposta final em `task.final_response`.

## Triagem

1. Verifique logs estruturados no Cloud Logging filtrando `service=adk-agent-orchestrator`.
2. Consulte métricas customizadas `custom.googleapis.com/adk_agent_orchestrator/*`.
3. Identifique se a falha está em modelo, tool local, MCP server, contrato ou runner.
4. Rode localmente:

```bash
pytest -q
python -m orchestrator.evaluation eval/datasets/phase5_smoke.json
```

## Mitigação

- Desabilite MCP server problemático removendo-o de `ADK_MCP_SERVERS`.
- Reduza `ADK_TOOL_TIMEOUT_SECONDS` se tools estiverem bloqueando execução.
- Faça rollback para a última revisão estável no Cloud Run/GKE.
- Se o contrato mudou, mantenha `contract_version` anterior ou restaure snapshot.

## Pós-incidente

- Adicione caso de regressão em `eval/datasets/`.
- Atualize snapshots de contrato somente com mudança versionada.
- Documente causa raiz, impacto, mitigação e follow-up.
