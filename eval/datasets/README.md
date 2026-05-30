# Evaluation datasets

Phase 5 datasets are JSON files that can run in CI without model credentials.
They validate contract/version expectations, workflow routing assumptions,
required capabilities, safety, estimated cost and latency budgets.

Run locally:

```bash
python -m orchestrator.evaluation eval/datasets/phase5_smoke.json
```

The legacy `meu-orquestrador` tests inspired the dataset style: objective,
expected workflow/capability behavior and execution-readiness assertions. The
new implementation does not import or port legacy classes.
