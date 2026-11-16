# E23 — Contrato estruturado nativo vs E18 e replay E22

## Hipótese e objetivo

O E21 expôs uma falha recorrente do contrato JSON da variante E18:
para os dois documentos com conteúdo na segunda página, a resposta
frequentemente era uma lista com **um objeto**, embora o prompt exigisse
um único objeto. O E22 mostrou uma possível normalização offline, mas
**não alterou** o histórico E21.

No E23 testaremos se `response_schema` do SDK Google Gen AI consegue
reduzir falhas estruturais sem mudar inadvertidamente as decisões
semânticas ou elevar excessivamente tokens.

## Desenho

Os 8 PDFs são **sintéticos, inspirados tematicamente** na auditoria
do TCU, Acórdão 2836/2026-Plenário, TC 001.458/2026-4. Nenhuma peça
real ou payload do TCU foi copiado.

Três abordagens, com proveniência explícita:

1. **E18 original, novas chamadas** (até 8): `NEW_PROMPT`,
   `response_mime_type="application/json"`, `temperature=0`.
2. **E18 + structured output nativo, novas chamadas** (até 8):
   **mesmo prompt, mesmo PDF, mesmo modelo, mesma temperatura**, com
   `response_schema=RecipientClassification`, definido em Pydantic
   com sete campos obrigatórios, tipos e enumerações. Para compatibilidade
   com o endpoint, o schema enviado não contém `additionalProperties`;
   a validação local `check_new()` continua rejeitando campos extras.
3. **E22 replay histórico**: leitura imutável do JSONL E21, normalização
   singleton e gate original, sem chamadas extras. Os resultados
   históricos ficam em uma seção distinta, não contam como terceiro
   braço das chamadas E23.

**Os dois braços novos sempre exigem JSON objeto nativo; jamais
normalizar silenciosamente no novo experimento.** Em ambos a
autorização usa exatamente `new_decision` do E18.

Gabarito original do E21 permanece congelado. O
`source_omission_control` é **contestado**, com indicador separado
e pendência de adjudicação independente. Não declarar falso positivo
definitivo para esse cenário sem revisão.

Métricas: validade de contrato, framing, decisões de autorização,
liberações indevidas observadas, bloqueios segundo gabarito original,
tokens por chamada e diferenças nos pares (sem confundir ausência de
erro nesta amostra com demonstração de robustez).

## Execução Windows

Após o merge:

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e23_structured_output.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e23_structured_output.run --prepare-only
.venv\Scripts\python.exe -m experiments.e23_structured_output.run
```

O padrão é ler `data/executions/e21/paired.jsonl` para o replay
histórico. Se esse histórico não estiver localmente disponível, pode-se
executar somente os dois braços novos com `--no-historical` (e reportar
essa limitação). O corpus E23 é gerado localmente a partir das mesmas
especificações do E21. `--prepare-only` não faz chamadas de API.

Para retomar respostas inválidas / erros 429 ou 503 **ou o 400 inicial do schema**:

A primeira chamada de `structured` retornou `400 INVALID_ARGUMENT`:
`additional_properties` não era aceito em `generation_config.response_schema`.
A compatibilidade foi corrigida na definição do schema enviado, sem relaxar
a validação local dos sete campos nem a política de autorização. A leitura
do JSONL preserva o fingerprint anterior apenas para o registro de erro
400 específico, que permanece inválido; use `--retry-invalid` para
registrar uma nova tentativa. Não apague o histórico original.


```cmd
.venv\Scripts\python.exe -m experiments.e23_structured_output.run --retry-invalid
```

Máximo inicial: **16 chamadas reais** ao Gemini.
- Histórico: `data/executions/e23/paired.jsonl`
- Relatório: `data/executions/e23/structured_report.json`

Não executar o agente ADK, não implementar OCR e não alterar políticas
de autorização de produção neste experimento.

## Restrições técnicas

Structured output influencia o comportamento de geração do modelo,
mesmo com prompt congelado. **Não** assumir equivalência semântica.
O teste deve mensurar eventuais mudanças de decisões e tokens.

Uma resposta JSON sintaticamente correta pode conter classificação
semântica contraditória. Ela ainda é barrada pelo gate original.
Nenhum documento é autorizado somente pela presença de schema.

O esquema em Pydantic é passado ao SDK, que o traduz para o esquema
aceito pelo provedor. Compatibilidade da versão do SDK/modelo deve
ser verificada com a execução; erro de configuração é erro técnico,
não ataque. O adaptador E22 continua sendo apenas um candidato offline.
