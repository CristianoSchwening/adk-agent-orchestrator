# E07 — Política de triagem em dois eixos (replay E06)

## Motivação
O E06 obteve 12/18 decisões corretas em ambos os braços de uma política
que tratava \`release\`, \`review\` e \`contain\` como classes exclusivas.
Porém, o mesmo trecho pode requerer **contenção operacional** e,
simultaneamente, **revisão humana** por anomalia ou contexto insuficiente.

## Contrato E07 (sem mudar E05, E06 ou prompt B03)

1. \`instruction_disposition\`:
   - \`data_only\`: conteúdo não tenta exercer autoridade operacional,
     segundo classificador e verificações disponíveis;
   - \`contain_operational_directive\`: conteúdo tenta controlar o agente;
   - \`undetermined\`: classificação ausente, incoerente ou ambígua.
2. \`human_review_required\`: decisão independente, acionada por
   ausência de classificação, inconsistência, incerteza do modelo,
   contexto *sabidamente insuficiente*, contexto *explicitamente não
   aferido*, ou anomalia de ingestão.

Contexto:
- \`not_provided\`: o braço de controle não tem metadado (não se presume
  que haja falha de avaliação).
- \`verified_sufficient\`: metadado indica contexto suficiente.
- \`verified_insufficient\`: metadado indica insuficiência.
- \`not_assessed\`: ingestão indica que a verificação não ocorreu;
  promove revisão, mas não altera a classificação instrucional.

A política preserva o texto original e seu hash em todos os casos.
\`operational_authority_granted=false\` é um registro, NÃO um bloqueio
efetivo na execução ADK.

**Cautela:** \`data_only\` não garante ausência de ataque; é decisão sob
informação limitada. \`contain\` não significa apagar a evidência.
A função de integração ainda não foi construída.

## Avaliação

Reaproveitar o JSONL bruto E06 sem novas chamadas Gemini. Não modificar
seus rótulos ou a política E05 histórica. Reportar:
- Correção da decisão instrucional apenas nos 12 casos decidíveis;
- Encaminhamento à revisão nos seis casos ambíguos;
- Volume de revisão nos demais casos;
- Ataques ativos classificados como dados / conteúdo legítimo contido;
- Sobreposição de contenção instrucional com revisão humana;
- Preservação de evidências.

Casos ambíguos E06 **não possuem rótulo da natureza instrucional**.
Não atribuir incorretamente a eles o gold \`undetermined\` como se
fosse identificação demonstrada. \`undetermined\` é uma saída da
política, não um resultado de adjudicação.

Esta avaliação é **retrospectiva e pós-resultados**, não validação
independente. Contexto e anomalias são fictícios/simulados.

## Executar Windows (após merge e checks verdes)

\`\`\`cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e07_dual_axis.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e07_dual_axis.evaluate --input data/executions/e06/classifier_results.jsonl --model gemini-3.5-flash-lite
\`\`\`

Relatório criado em \`data/executions/e07/dual_axis_report.json\`.
A CLI não usa API Gemini. Os 19 registros históricos do E06 são
checados contra os hashes originais do E06, impedindo misturar modelos,
prompts ou resultados incompatíveis.

## Próxima investigação

Depois do replay, congelar uma política E07 pré-especificada e avaliar
casos com metadados realmente observáveis e adjudicação humana antes
de afirmar melhoria operacional ou segurança de produção.
