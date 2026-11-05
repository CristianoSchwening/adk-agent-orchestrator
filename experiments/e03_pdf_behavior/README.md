# E03 — Efeito comportamental da ingestão de PDFs

**Pergunta:** uma instrução ativa, extraída do PDF mas invisível na
renderização PyMuPDF, altera os campos do agente jurídico em comparação
com uma peça visualmente idêntica sem a instrução?

## Desenho

Três PDFs sintéticos com os mesmos três lançamentos de R$ 2.000,00 e
valor alegado de R$ 6.000,00 em P-004:
- \`control\`: fatos, sem instrução;
- \`hidden_active\`: mesmos fatos e instrução operacional com
  \`render_mode=3\`, que o PyMuPDF extrai mas não renderiza;
- \`visible_quoted\`: mesmos fatos e instrução citada visivelmente como
  objeto de auditoria, não como ordem.

A condição citada é um **controle semântico**, não um PDF visualmente
idêntico. A comparação de paridade visual é apenas
\`control\` versus \`hidden_active\`.

O executor gera os PDFs, compara renderização por hashes dos pixels,
confirma a diferença no texto extraído e preservação dos fatos;
**falha antes de chamar o Gemini** se algum invariante não for atendido.

A aplicação envia \`page.get_text("text", sort=False)\` por JSON ao
agente E01, não envia PDF binário. Usa a mesma instrução do agente E01,
mesma tarefa JSON e mesma rubrica do E02, sem classificador ou defesa
adicional. A avaliação registra valores, fontes, \`null\` versus \`0\`,
contratos inválidos e desvios contra o controle.

## Executar após merge no Windows

\`\`\`cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e03_pdf_behavior.py -q --basetemp=data/pytest_temp
\`\`\`

Gerar e validar PDFs **offline** antes de consumir a API:

\`\`\`cmd
.venv\Scripts\python.exe -m experiments.e03_pdf_behavior.run --prepare-only
\`\`\`

Smoke test:

\`\`\`cmd
.venv\Scripts\python.exe -m experiments.e03_pdf_behavior.run --model gemini-3.5-flash-lite --max-cases 1
\`\`\`

Rodada completa e retomada:

\`\`\`cmd
.venv\Scripts\python.exe -m experiments.e03_pdf_behavior.run --model gemini-3.5-flash-lite --pause-seconds 15
\`\`\`

Depois, opcionalmente, \`--repetitions 3\` para repetibilidade.

Arquivos locais:
- \`data/experiments/e03/E03_*.pdf\`
- \`data/experiments/e03/extraction_diagnostic.json\`
- \`data/executions/e03/behavioral_results.jsonl\`
- \`data/executions/e03/behavioral_report.json\`

## Limites e interpretação

Resultados com JSON inválido são preservados no histórico mas não pontuados;
repetições válidas mantidas na retomada. Hashes de PDF e prompt impedem misturar
configurações. O experimento usa texto extraído, não OCR ou visão e não testa
a leitura de PDF nativa do Gemini. Uma omissão de fontes ou alteração de
valor não prova, isoladamente, obediência ao comando. É uma amostra sintética,
com proteção E01 já presente; **não certifica segurança para produção**.
