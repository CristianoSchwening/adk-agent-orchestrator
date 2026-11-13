# E19 — Estabilidade das decisões do classificador (E18 congelado)

## Objetivo

Investigar se os falsos bloqueios observados no E17/E18 são **persistentes**
ou variam entre chamadas. Não modificar prompts, contratos ou políticas.

Cada execução E19 é uma chamada **nova** ao Gemini com o mesmo PDF nativo
e o mesmo modelo utilizado no E18. Dois braços:
- `control`: E14b/E15 + política E15;
- `recipient_aware`: E18 + política experimental E18.

Rodada padrão: 5 documentos E18 relevantes para erros, controles,
citações e um ataque ativo; **duas repetições frescas** em cada braço,
totalizando 20 chamadas. `--all-cases` amplia para 8 documentos (32 chamadas).
O histórico E18 não é reaproveitado como repetição E19.

Indicadores: alternância de autorização entre repetições, variação
dos enquadramentos, falsos bloqueios, liberações indevidas, contratos
válidos e consumo de tokens. Erros de API permanecem pendentes.

## Windows após merge

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e19_classifier_stability.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e19_classifier_stability.run --prepare-only
.venv\Scripts\python.exe -m experiments.e19_classifier_stability.run
```

Para continuar após erro 503/429:

```cmd
.venv\Scripts\python.exe -m experiments.e19_classifier_stability.run --retry-invalid
```

Artefatos: `data/executions/e19/replications.jsonl` e
`data/executions/e19/stability_report.json`.

É um estudo sintético exploratório, não uma medição de confiabilidade em
produção. Não executa agente jurídico nem adiciona extrator/OCR.
A modalidade gratuita depende das cotas da conta Google.
