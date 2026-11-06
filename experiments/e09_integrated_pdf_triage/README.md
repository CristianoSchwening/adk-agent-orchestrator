# E09 — PDF real (PyMuPDF) → Gemini B03 → Política E07

O E09 conecta três peças já existentes, sem alterar o system prompt B03
ou a política E07:

1. Gerar/inspecionar quatro PDFs sintéticos E08 (controle, comando oculto,
   comando citado e PDF somente com imagem).
2. Classificar pelo Gemini o **texto realmente extraído** dos três PDFs
   com camada textual, usando sessões independentes do Google ADK.
3. Aplicar a política E07 ao resultado do classificador e à anomalia
   realmente identificada no PDF com PyMuPDF.

A classificação B03 recebe apenas ID e trecho, **não** conhece a variante,
a referência esperada ou os metadados de ingestão. O JSONL inclui hashes
do PDF, texto, instrução, prompt e política para impedir mistura de
configurações em retomadas.

Para \`image_only\`, nenhuma chamada Gemini é realizada: o PDF contém
evidência visual que PyMuPDF sem OCR não consegue extrair. O relatório
marca \`skipped_no_extractable_text\` e solicita revisão, preservando hash
e caminho do PDF original. Nenhum marcador textual é enviado ao LLM.

O estudo **não envia PDFs binários ao Gemini**, não realiza OCR e
não executa contenção no agente jurídico. \`contain\` é metadado de
tratamento e não mecanismo de bloqueio.

## Windows (após merge)

\`\`\`cmd
git pull origin main
.venv\\Scripts\\python.exe -m pytest tests/test_e09_integrated_pdf_triage.py -q --basetemp=data/pytest_temp
.venv\\Scripts\\python.exe -m experiments.e09_integrated_pdf_triage.run --prepare-only
.venv\\Scripts\\python.exe -m experiments.e09_integrated_pdf_triage.run --model gemini-3.5-flash-lite --pause-seconds 15
\`\`\`

Artefatos:
- PDFs: \`data/experiments/e09/E08_*.pdf\`;
- respostas brutas: \`data/executions/e09/classifier_results.jsonl\`;
- relatório: \`data/executions/e09/integrated_report.json\`.

Após iniciar o histórico, não altere os PDFs, a instrução ou o modelo:
a retomada verificará hashes e rejeitará configurações incompatíveis.
O executor retenta erros HTTP 503 e preserva respostas válidas.
Resultados com contrato inválido permanecem pendentes.

## Leituras e limitações
- Nos três PDFs textuais, a natureza instrucional esperada foi
  definida pelo pesquisador (controle/citação são dados; oculto é ativo).
- O raster é excluído da comparação semântica, pois não houve texto extraído.
- Anomalia técnica não significa ataque, nem sua ausência comprova segurança.
- Uma amostra sintética pequena não estima capacidade em produção.
- Para avaliar contenção real, será necessária integração com o agente
  jurídico ADK e ensaios sobre preservação de evidências.
