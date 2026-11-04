# A01 — Diagnóstico somente-leitura de PDFs

Este analisador **não chama Gemini**, não modifica os PDFs de entrada e não
bloqueia nem remove conteúdo. Ele compara imagem renderizada, texto extraído
e sinais estruturais de invisibilidade (tipo de texto 3 e opacidade zero).

## Execução em Windows CMD

Após o merge do PR e `git pull origin main`, instale as dependências
de desenvolvimento no ambiente virtual existente, caso necessário:

```cmd
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Com os PDFs sintéticos anteriores ainda disponíveis, execute:

```cmd
.venv\Scripts\python.exe -m experiments.pdf_representation.analyze --control data/experiments/e01/c03/controle.pdf --candidate data/experiments/e01/c03/adversarial.pdf
```

Se esses PDFs foram excluídos, use **qualquer par sintético controlado**
passando seus caminhos nos argumentos `--control` e `--candidate`.
O script não presume que os nomes ou diretórios sejam fixos.

## Saída

`data/executions/pdf_representation/a01_report.json`: versão do PyMuPDF,
hashes do PDF e do texto, renderizações por página, texto extraído integral,
spans sinalizados com página, bbox, seqno, layer, opacidade e tipo de texto;
contagens de tipos de objetos pintados; comparação de evidências.

`candidate_flagged_spans` representa sinais técnicos, **não detecção de ataque**.
O protocolo ainda não diagnostica oclusão geométrica, OCG, cropbox e OCR legítimo;
esses itens pertencem aos cenários posteriores da matriz.

O indicador `legitimate_content_preserved` verifica apenas a presença dos
marcadores JAN/FEV/MAR e R$ 6.000,00, não uma validação semântica geral.

## Testes offline

```cmd
.venv\Scripts\python.exe -m pytest tests/test_pdf_representation_a01.py -q
```

Os testes criam PDFs temporários benignos e não exigem os PDFs locais do E01.
