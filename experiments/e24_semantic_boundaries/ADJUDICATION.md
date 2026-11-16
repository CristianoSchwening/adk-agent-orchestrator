# Adjudicação independente do E24

Este pacote operacionaliza a etapa de revisão cega da [consolidação E24](../../docs/research/E24-evidence-and-adjudication.md).

## Objetivo

Distinguir `active`, `quoted`, `none` e `uncertain` em 12 PDFs sintéticos do E24. Os revisores devem identificar o **destinatário real** do comando e o contexto documental, sem consultar prompts, gabaritos do autor ou respostas do Gemini.

## Preparação (sem API)

Depois de aprovar o CI e integrar esta PR:

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e24_adjudication.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e24_semantic_boundaries.adjudicate prepare
```

O comando cria `data/executions/e24/adjudication/manifest.json`, `review_R1.json` e `review_R2.json`. Os campos de julgamento começam vazios. **Não cria gabaritos, não atribui respostas automaticamente, não lê relatórios de classificação e não chama Gemini nem ADK.** Os PDFs locais precisam estar disponíveis em `data/experiments/e24` (são gerados de maneira determinística se ausentes).

Entregue os PDFs e apenas a ficha correspondente a **cada um de dois revisores distintos**. Não compartilhe o gerador ou os relatórios do E24 com os revisores. Cada um preenche sua ficha: `reviewer_id`, `label`, `recipient`, `evidence`, `page`, `justification`. Para `active` e `quoted`, são obrigatórios evidência e página. Para ambiguidades, usar `uncertain` com justificativa.

O preparo recusa sobrescrever arquivos já existentes.

## Comparação offline

Após receber as duas fichas completas:

```cmd
.venv\Scripts\python.exe -m experiments.e24_semantic_boundaries.adjudicate compare
```

Isso gera `comparison.json`, **sem reescrever as fichas** e sem resolver automaticamente discordâncias. O comparador verifica IDs, hash dos PDFs, identidade distinta dos revisores, completude e campos válidos. A saída contém concordâncias, discordâncias e a lista pendente de adjudicação, **não** um gabarito final.

Próxima etapa após a revisão: uma pessoa adjudicadora registra divergências ou mantém `uncertain`; gerar um gabarito adjudicado versionado **separado**, preservando as saídas anteriores e os rótulos provisórios. Somente depois recalcular os indicadores semânticos e decidir arquitetura.

Também há duas pendências fora deste pacote: `source_omission_control` do E21/E23 precisa de revisão independente; `priority_override_control` do E23 continua como caso obrigatório de regressão.

## Restrições e cuidados

- A avaliação humana é independente somente se os revisores não tiverem acesso aos rótulos do autor nem às saídas dos classificadores.
- Comparar fichas não substitui uma adjudicação conclusiva.
- PDFs e conteúdo jurídico são **sintéticos**, não peças judiciais reais.
- Nenhuma alteração em `new_decision`, schema E23, prompts E18, autorização ou código ADK.
