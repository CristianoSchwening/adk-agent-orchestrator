# E08 — Proveniência e sinais verificáveis de ingestão PDF

## Hipótese
Sinais técnicos de extração podem indicar que a leitura precisa de revisão,
**sem** inferir que o documento contém uma instrução maliciosa.

Quatro PDFs sintéticos:
1. Controle textual, com dados fictícios preservados.
2. Mesma renderização com operação `ignore-text` (modo 3), contendo
   texto adicional extraído pelo PyMuPDF.
3. Citação visível de uma instrução, com renderização e extração diferentes.
4. PDF rasterizado, com texto apresentado visualmente mas **sem texto
   retornado por `get_text("text")`**, pois OCR não é executado.

## Sinais observáveis
- Operações `ignore-text` de `page.get_bboxlog()`, independentemente da
  semântica do texto;
- Imagem presente com texto extraído vazio;
- Hash SHA-256 do arquivo, texto extraído e rasterização por página;
- Comparações de paridade entre controles, com invariantes explícitas;
- Texto original extraído e localização por página.

Esses sinais **não** detectam todas as possíveis formas de ocultação,
nem provam um ataque, uma ordem válida ou a necessidade jurídica de OCR.

## Demonstração da política E07
O campo `ingestion_anomaly` vem dos sinais técnicos do PDF. Para
demonstrar o roteamento E07 sem API, o programa usa **classificações
sintéticas simuladas** do E05. Isso não constitui detecção real de
intenção maliciosa e não mede qualidade do Gemini.
Em `image_only`, não há classificação de texto. Um marcador explícito
de ausência é usado apenas na chamada demonstrativa à política; a
evidência original permanece no arquivo PDF com hash registrado.

## Windows (após merge)
```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e08_pdf_ingestion.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e08_pdf_ingestion.run
```

Relatório: `data/executions/e08/ingestion_report.json`.
PDFs: `data/experiments/e08/E08_*.pdf`.

## Limitações e próximos critérios
- A paridade de renderização foi verificada exclusivamente no PyMuPDF.
- PDFs digitais reais podem ter camadas, máscaras, anotações, formulários
  e outras construções que este corpus não cobre.
- Texto invisível pode ser benigno; falta de texto extraído pode ser
  problema de representação e não ação de atacante.
- A análise não interpreta juridicamente trechos e não realiza OCR.
- Reavaliar métricas com casos negativos legítimos e tipos novos de
  falha antes de conectar decisões a um agente em produção.
- A contenção runtime continua não implementada no ADK.
