# E14 — Leitura PDF nativa do Gemini versus extração PyMuPDF

## Diretriz arquitetural

Priorizar capacidades nativas do provedor de IA em vez de desenvolver
extrator, OCR ou sanitizador próprios. O PyMuPDF permanece **apenas no
braço experimental de referência** e na construção dos PDFs sintéticos.
A aplicação final não depende dele.

Dois braços são executados com **o mesmo modelo, tarefa e system prompt**:
1. `native_pdf` envia os bytes PDF originais como `application/pdf`
   usando a API oficial `google.genai.Client.models.generate_content`;
2. `reference_extracted_text` envia somente `page.get_text("text")`.

O prompt busca fatos, fontes e eventual texto dirigido à IA. O estudo
compara os relatos do modelo — não revela seus estados internos.
Texto oculto não relatado não significa não processado. Comando
detectado não implica obediência. A supressão de fonte é medida como
desvio observável, sem atribuir causalidade automaticamente.

## Corpus e escopo

Reutiliza PDFs sintéticos de E12 e E13. Primeira rodada padrão:
`e12__render_mode_3`, `e12__white_on_white`,
`e13__mixed_page`, `e13__raster_page` (8 chamadas = 4 pares).
Para expandir, use `--max-cases 10` (20 chamadas, dependendo da cota).
`--case-id` seleciona casos específicos sem alterar os prompts.
Os arquivos do corpus são armazenados em data/experiments/e14.
Histórico e comparação são mantidos em arquivos separados.

## Modelo gratuito e privacidade

Modelo padrão: `gemini-2.5-flash-lite`, com opção de modalidade
gratuita publicada pelo Google (cotas variáveis por projeto/região).
O script **não faz upgrade de plano**, não chama ferramentas
pagas e interrompe a execução no primeiro erro de API.
Não há garantia de que a conta tenha acesso gratuito disponível.

**IMPORTANTE:** o nível gratuito do Gemini pode permitir uso dos
dados para aprimorar serviços. Use APENAS PDFs sintéticos, nunca
documentos jurídicos confidenciais, sem revisar os termos e controles
de tratamento de dados.

## Windows (após merge)

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e14_native_pdf.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e14_native_pdf.run --prepare-only
.venv\Scripts\python.exe -m experiments.e14_native_pdf.run
```

Para rodar o mesmo modelo anterior, se disponível e dentro da cota,
informe `--model gemini-3.5-flash-lite`. Confirme o tier antes de usar
modelos alternativos.

Saídas:
- `data/experiments/e14/e12/` e `data/experiments/e14/e13/`;
- `data/executions/e14/native_comparison.jsonl` (respostas completas);
- `data/executions/e14/comparison_report.json` (métricas comparativas).

Retomada verifica hashes de PDF, texto, prompt, system prompt e modelo.
A execução padrão reutiliza histórico; `--retry-invalid` permite
retentar respostas inválidas explicitamente, consumindo nova cota.

## Limitações

Sem PDFs reais do TCU, sem contenção ADK, sem detecção independente de
instruções, e sem estimativa de robustez em produção. O instrumento do
experimento não autoriza automaticamente nenhum documento.
Os dois modos podem ser processados internamente de maneiras distintas
pelo provedor; não há acesso à representação interna.
Documentação do provedor:
- https://ai.google.dev/gemini-api/docs/generate-content/document-processing
- https://ai.google.dev/gemini-api/docs/pricing
