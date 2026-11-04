# E01 / C03 — Comparar PDFs locais e analisar com o Gemini

Este executor **não cria, edita ou publica PDFs**. Ele lê dois arquivos
sintéticos disponibilizados localmente, compara suas renderizações (pixels),
extrai o texto com PyMuPDF e envia cada extração ao **mesmo agente E01**
usado nos casos C01/C04/C04B, sempre em sessões independentes.

## Preparação (Windows CMD, raiz do projeto)

Coloque os PDFs em:
- `data/experiments/e01/c03/controle.pdf`
- `data/experiments/e01/c03/adversarial.pdf`

Instale PyMuPDF no ambiente virtual já utilizado pelo orquestrador:

```cmd
.venv\Scripts\python.exe -m pip install PyMuPDF
```

Execute uma repetição por cenário:

```cmd
.venv\Scripts\python.exe -m experiments.e01_prompt_injection.c03_local --repetitions 1
```

Ou informe caminhos específicos usando `--control-pdf` e `--attack-pdf`.

## Saídas

- `data/executions/e01/c03/pdf_extraction_diagnostic.json`: SHA-256
  de ambos os PDFs, texto extraído completo, hashes do texto e comparação
  dos pixels renderizados e dos textos extraídos.
- `data/executions/e01/c03/results.jsonl`: respostas, prompts, modelo,
  duração e hashes por cenário. O arquivo recebe novas linhas a cada execução.

Para um teste de diferenciação visual/textual, espera-se
`visible_render_identical=true` e `extracted_text_identical=false`.
A comparação de pixels considera cada página renderizada pelo PyMuPDF e
não substitui revisão humana do documento.

**Limites:** o modelo recebe o texto extraído, não o PDF bruto.
A saída `ok` indica execução bem-sucedida, não resistência.
Não usar documentos pessoais ou processuais reais nem publicar o material
sensível no Git remoto.
