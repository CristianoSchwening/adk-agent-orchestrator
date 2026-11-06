# E05 — Política de triagem documental (protótipo offline)

## Pergunta
Como formalizar três decisões auditáveis — **release**, **review** e
**contain** — sem confundir classificação de intenção, execução de um ataque,
e preservação das evidências jurídicas?

Esta etapa **não** cria uma defesa em produção, **não** chama o Gemini,
**não** modifica o agente ADK e **não** apaga texto do PDF.

## Contrato

Entradas: ID da fonte, trecho integral original, classificação B03 válida
(quando disponível), \`context_complete\` e \`ingestion_anomaly\`.
O contexto e a anomalia vêm de etapas independentes de ingestão/revisão,
**não** dos rótulos secretos do corpus B04.

Saídas:
- \`release\`: trecho classificado como dado/citação/pedido legítimo, sem
  contradição nem sinal de incerteza; preserva texto.
- \`review\`: classificação ausente/inválida, sinais contraditórios,
  enquadramento ambíguo, revisão pedida, contexto sabidamente insuficiente
  ou anomalia de ingestão.
- \`contain\`: tentativa ativa de interferência operacional com
  classificação válida/coerente. O texto continua preservado como
  evidência, mas a política marca sua autoridade operacional como negada.

**Precedência:** qualquer motivo para revisão prevalece até sobre
uma classificação ativa. Este é um trade-off intencional a avaliar
empiricamente, não uma conclusão de segurança validada.

\`result_for_downstream\` gera um envelope com evidência original, hash,
ação proposta, metadados de revisão e \`operational_authority=denied\`.
A função **não impede, por si só**, que um consumidor ignore o sinal.
É indispensável implementar e testar a fronteira de confiança em uma
integração posterior, separando armazenamento/auditoria da autoridade
do texto fornecido ao agente.

## Execução offline (após merge)

\`\`\`cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e05_document_triage.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e05_document_triage.run
\`\`\`

Relatório: \`data/executions/e05/offline_demo.json\`.
Os exemplos são **fixtures sintéticas simuladas**: nenhuma é uma
previsão real do B03/B04 e suas saídas não devem ser contadas como
acurácia, recall, taxa de contenção ou evidência de desempenho do Gemini.

## Critérios para o estudo seguinte

1. Rodar o classificador congelado sobre um corpus novo e
   adjudicado independentemente (incluindo ambiguidades).
2. Medir separadamente falsos positivos, falsos negativos, cobertura
   de revisão e decisões incorretas de liberação/contenção.
3. Testar como uma integração realmente impede autoridade operacional
   de instruções documentais **sem perder fatos e fontes**.
4. Registrar decisão do revisor e avaliar possíveis falsos bloqueios,
   latência, custo e rastreabilidade.
5. Congelar política e critérios antes de ver respostas do novo holdout.

Nada aqui substitui avaliação humana jurídica ou validação de segurança
para um ambiente real.
