# E22 — Recuperação conservadora de JSON, offline

## Problema observado no E21

Em documentos de **duas páginas**, o classificador E18 retornou
repetidamente uma lista com **um objeto** como resposta JSON, apesar
de o contrato solicitar um objeto isolado. O histórico E21 continua
válido como evidência de **falha de contrato original**; não reescrever
as respostas nem reinterpretar esses casos como sucesso do E21.

## Hipótese

Uma etapa determinística de compatibilidade pode recuperar o conteúdo
estrutural de `[ {...} ]` **somente** quando:
1. a resposta veio de E18, com `status=ok`;
2. o elemento único é exatamente um objeto E18 estruturalmente válido;
3. o `new_decision` original continua decidindo a autorização.

Listas vazias/múltiplas, elementos inválidos, falhas de API,
classificador de controle E15 e contradições semânticas não podem
produzir autorizações novas por coerção estrutural.

## Seleção sem viés de tentativas

Todas as tentativas do JSONL original são auditadas. Havendo um registro
originalmente válido, usa-se o último válido (equivalente ao replay E21).
Caso só existam respostas recuperáveis, usa-se a **primeira recuperável**,
não a resposta mais favorável. O relatório registra todas as tentativas,
a distribuição de decisões recuperáveis e divergências entre elas.

A normalização permite comparar um candidato técnico; ela **não**
reclassifica o resultado original do E21, não aumenta a capacidade
semântica do Gemini e não implementa o gate em produção.

## Windows

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e22_json_contract_normalization.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e22_json_contract_normalization.run
```

O script lê `data/executions/e21/paired.jsonl` e escreve
`data/executions/e22/normalization_report.json`. Não exige PDF,
chave de API, Gemini ou OCR.

Gabarito de `source_omission_control` continua **não adjudicado**:
a frase sobre o que o relatório técnico deve registrar pode ser
interpretada como orientação documental ou interferência operacional.
Manter separadas a avaliação de estrutura, de semântica e de segurança.
