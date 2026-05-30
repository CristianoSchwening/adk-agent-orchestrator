# Runbook — Atualização de agentes

## Antes da mudança

1. Revise instruções do root agent e workflows ADK.
2. Adicione ou atualize casos em `eval/datasets/`.
3. Rode localmente:

```bash
pytest -q
ruff check .
python -m compileall -q src tests
python -m orchestrator.evaluation eval/datasets/phase5_smoke.json
```

## Durante a mudança

- Não reintroduza runtime legado (`Workforce`, `TaskBoard`, `Subtask`, `Toolkit`).
- Preserve o contrato público ou incremente `contract_version`.
- Mantenha tools destrutivas fora da execução padrão.
- Documente novos riscos de HITL, MCP e custo.

## Depois da mudança

1. Publique em staging.
2. Execute datasets determinísticos e, quando disponível, datasets online.
3. Compare métricas de latência, erro, custo e qualidade com baseline.
4. Promova para produção gradualmente.
5. Atualize README, arquitetura e snapshots quando necessário.
