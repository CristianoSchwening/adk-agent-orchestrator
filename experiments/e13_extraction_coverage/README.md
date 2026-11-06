# E13 — Cobertura e integridade da extração documental

O E12 identificou que um PDF pode preservar todos os fatos avaliados e ainda perder uma página rasterizada inteira. O E13 separa **segurança da representação** (texto oculto, branco, encoberto) de **cobertura da ingestão** (imagem sem OCR, conteúdo gráfico não verificado, página sem conteúdo extraível).

O corpus fictício contém sete variantes: texto controle, página rasterizada, página mista texto+imagem, tabela desenhada com vetores e células de texto, texto encoberto por forma opaca, texto branco e página em branco.

Uma referência sintética de fatos esperados, definida antes da execução e **mantida fora do detector**, permite contar perdas conhecidas no experimento. Na produção tal gabarito normalmente não existe: nenhum documento é marcado como completamente verificado só porque não apresentou sinais.

## Estados
- `no_mechanical_gap_detected_not_verified_complete`: nenhum sinal conhecido; não equivale a cobertura total.
- `requires_review_or_additional_extraction`: ao menos uma limitação detectada; não implica ataque nem perda comprovada.

Imagens, texto branco, possível sobreposição, vetores e páginas vazias geram motivos distintos. `security_representation_signals` e `extraction_coverage_signals` são eixos separados. Nenhuma projeção é liberada ao agente.

## Executar (Windows, após merge)

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e13_extraction_coverage.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e13_extraction_coverage.run
```

PDFs: `data/experiments/e13/E13_*.pdf`
Relatório: `data/executions/e13/coverage_report.json`

## Limites
Sem OCR, Gemini, adjudicação humana, validação de documentos reais ou liberação automática. Heurísticas de contraste e sobreposição são indicativas. Vetores podem ser decoração. Não é sanitizador nem garantia de extração integral.
