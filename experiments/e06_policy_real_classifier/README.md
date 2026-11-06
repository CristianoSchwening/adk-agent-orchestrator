# E06 — Classificação real + política de triagem E05

## Objetivo

Avaliar, sem ajustes após observar resultados, as decisões de \`release\`,
\`review\` e \`contain\` quando a política E05 recebe **saídas reais** do
classificador Gemini com a instrução B03 congelada.

Este E06 **não** aplica contenção real ao agente jurídico: avalia a
decisão que uma integração futura deveria respeitar.

## Corpus e referência

- 18 trechos sintéticos inéditos e fixos no código antes das chamadas:
  seis \`release\` (legítimos e citações), seis \`contain\` (instruções
  ativas) e seis \`review\` (contexto deliberadamente insuficiente).
- Rótulos esperados escritos pelo pesquisador: não são avaliações de
  juristas independentes e não caracterizam holdout externo verdadeiro.
- Classificador recebe somente \`case_id\` e \`excerpt\` conforme B03,
  sem rótulo, metadado ou explicação da decisão esperada.
- Metadados de contexto e anomalia de ingestão são **simulados** e
  registrados antes da execução, inclusive em casos não ambíguos.
  Não são sensores reais nem inferências independentes.
- Mesmas respostas Gemini para dois braços comparáveis:
  1. \`baseline_classifier_only\`: política E05 sem metadados extras.
  2. \`metadata_augmented\`: mesma política com contexto/anomalia do corpus.
- Política E05 e INSTRUCTION/build_prompt/validate_output de B03 importados
  diretamente. Histórico bloqueia mudanças em corpus, prompt, versão da
  política e modelo via hashes.

## Métricas

Matriz de confusão de três decisões por braço. Separar:
- \`unsafe_release_of_active\`: comando ativo liberado automaticamente;
- \`unnecessary_containment_of_legitimate\`: evidência legítima contida;
- \`ambiguous_not_reviewed\`: contexto insuficiente liberado ou contido
  sem revisão;
- \`ambiguous_reviewed\`: casos de contexto insuficiente revisados;
- \`active_sent_to_review\` e \`legitimate_sent_to_review\`: custo de revisão.

O relatório também registra mudança positiva/negativa de decisão entre
braços e preservação do trecho original. Não interpretar \`contain\` como
bloqueio real, nem o percentual correto como taxa de robustez de produção.

## Windows (após merge e checks verdes)

\`\`\`cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e06_policy_real_classifier.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e06_policy_real_classifier.run --model gemini-3.5-flash-lite --max-cases 1
.venv\Scripts\python.exe -m experiments.e06_policy_real_classifier.run --model gemini-3.5-flash-lite --pause-seconds 15
\`\`\`

Uma vez concluída a primeira rodada, mais duas por condição:
\`\`\`cmd
.venv\Scripts\python.exe -m experiments.e06_policy_real_classifier.run --model gemini-3.5-flash-lite --repetitions 3 --pause-seconds 15
\`\`\`

Dados (locais, fora do Git):
- \`data/executions/e06/classifier_results.jsonl\`: histórico bruto de
  chamadas e validação do JSON.
- \`data/executions/e06/triage_report.json\`: matrizes por braço, pares,
  métricas de revisão, erros, pendências e hashes.

As execuções são retomáveis, com até três tentativas em erros HTTP 503
e persistência por resposta. Saídas com contrato inválido ficam pendentes.

## Próxima etapa, condicionada aos resultados

Adjudicar rótulos por avaliadores independentes, avaliar corpus real
anonimizado quando permitido e testar uma integração capaz de impedir
a autoridade operacional de trechos suspeitos sem eliminar as
informações probatórias legítimas.

Não usar o resultado deste corpus para ajustar o prompt e simultaneamente
reivindicar validação independente.
