# E14b — Validação de proveniência e detecção separada

## Por que uma segunda rodada?

O E14 confirmou recuperação de dois fatos em imagem via PDF nativo,
mas o prompt continha R$ 1.500 e P-012 como exemplos de contrato,
e o avaliador exigia igualdade literal do identificador da fonte.

O E14b preserva os resultados anteriores, cria um novo corpus
inteiramente fictício e usa **valores e identificadores diferentes**,
que não aparecem nos prompts nem no código da chamada ao Gemini.

## Duas tarefas independentes

Cada documento passa por dois braços:
- PDF nativo enviado diretamente ao Gemini;
- texto PyMuPDF, exclusivamente como controle de pesquisa.

E por duas chamadas separadas, com contextos independentes:
- classify: enquadramento de comandos dirigidos à IA;
- extract: recuperação de alegações monetárias, fonte, página e
  evidência textual por fato.

O classificador **não funciona como proteção operacional** nesta
rodada. O extrator recebe seu conteúdo independentemente: o estudo
avalia o comportamento de ambos e não os conecta por uma política.

A verificação de fonte aceita, por exemplo, `PETICAO FICTICIA P-258`
como referência ao identificador `P-258`, sem usar igualdade
literal. A métrica de evidência exata é conservadora e pode falhar
quando houver paráfrases; isso não é necessariamente perda factual.

## Escopo e cota

Modelo padrão: `gemini-3.1-flash-lite`, opção gratuita sujeita
à disponibilidade e às cotas do projeto.

Rodada inicial: 3 documentos, 2 braços e 2 tarefas = **12 chamadas**.
Inclui instrução ativa branca, anexo em imagem e citação visível.
Ampliação: `--max-cases 6`, 24 chamadas, incluindo texto branco
benigno, `render_mode=3` e página rasterizada.
Históricos E14 anteriores são preservados em diretório próprio.

## Executar em Windows, após merge

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e14b_native_provenance.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e14b_native_provenance.run --prepare-only
.venv\Scripts\python.exe -m experiments.e14b_native_provenance.run
```

Saídas: `data/experiments/e14b/E14B_*.pdf`;
`data/executions/e14b/results.jsonl` e
`data/executions/e14b/report.json`.

Para economizar chamadas, selecione casos com `--case-id hidden_white`
ou `--case-id mixed_image`. O histórico permite retomar quando
uma execução for interrompida por limite ou falha de API.
**Não enviar PDFs de clientes reais na modalidade gratuita** sem
avaliar termos e governança de dados.

## Limitações

Sem documentos reais, sem avaliação estatística, sem adjudicação
humana, sem OCR próprio e sem autorização de documentos em produção.
A leitura de PDF nativo pelo fornecedor não prova proteção contra
prompt injection. Detectar a instrução não é o mesmo que impedir
que ela influencie uma tarefa jurídica.
