# E11 - Contencao seletiva com preservacao probatoria

Hipotese: em um PDF sintetico controlado, pode-se separar operacoes
de texto nao renderizado e fornecer ao agente apenas fatos visiveis,
preservando PDF e trechos isolados para auditoria.

O projeto utiliza PyMuPDF get_texttrace: type=3 e isolado, type=0 e
reconstruido. Qualquer operador nao previsto provoca recusa. Para
autorizar a analise experimental, a projecao deve ser identica ao
texto do PDF de controle. Esta condicao e um ORACULO SINTETICO,
que geralmente nao existe em documentos reais.

O original continua marcado para revisao e nunca e liberado
automaticamente. A nova chamada ao agente E01 recebe apenas a
projecao verificada. O relatorio compara com baseline e gate inteiro
do E10, reusando os arquivos existentes com hashes conferidos.

## Executar apos aprovar e integrar a PR, na raiz do projeto

    git pull origin main
    .venv\Scripts\python.exe -m pytest tests/test_e11_selective_containment.py -q --basetemp=data/pytest_temp
    .venv\Scripts\python.exe -m experiments.e11_selective_containment.run --prepare-only
    .venv\Scripts\python.exe -m experiments.e11_selective_containment.run --model gemini-3.5-flash-lite

Pre-requisitos:
- data/executions/e09/classifier_results.jsonl
- data/executions/e10/gate_report.json

Artefatos:
- data/experiments/e11/E08_*.pdf
- data/executions/e11/selective_report.json

A solucao nao e sanitizador geral nem filtro de seguranca em
producao. Outras tecnicas de ocultacao, documentos complexos, OCR,
revisao humana e liberacao posterior nao estao implementados.
