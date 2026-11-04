# Frente A — Discovery de ingestão e representação de PDF

**Estado:** protocolo proposto, ainda não executado.  
**Origem:** E01 / C03 demonstrou renderização visual equivalente com extração textual diferente.  
**Escopo:** arquivos integralmente sintéticos; diagnóstico local e determinístico antes de envolver LLM.

## Pergunta central

Como reconhecer divergências entre o PDF renderizado e a representação textual
consumida pelo agente **preservando dados legítimos** e sem confundir texto não
renderizado com tentativa maliciosa?

## Hipóteses

- **HA1 — Observabilidade:** metadados estruturais do PDF permitem identificar
  condições em que o extrator retorna texto não exibido normalmente.
- **HA2 — Classificação cautelosa:** a invisibilidade, sozinha, não permite afirmar
  que existe prompt injection. Camadas OCR invisíveis são um contraexemplo legítimo.
- **HA3 — Fidelidade:** a inspeção pode registrar spans, posições, modos e fontes
  sem removê-los do conjunto de evidências nem alterar o conteúdo original.
- **HA4 — Triagem:** divergências técnicas podem ser priorizadas para revisão
  humana por critérios explícitos; nenhum bloqueio automático neste estágio.

## Matriz inicial de cenários

| ID | Situação | Observável técnico | Possível uso legítimo | Questão |
| --- | --- | --- | --- | --- |
| A01 | Texto com modo de renderização 3 (Tr=3) | `get_texttrace()` span `type=3`; `get_bboxlog()` `ignore-text` | OCR pesquisável | Texto extraído não visível? |
| A02 | Texto totalmente transparente | `opacity=0` | Elementos auxiliares de acessibilidade / edição | Detectável sem falsos positivos? |
| A03 | Texto encoberto por objetos posteriores | `seqno`, bboxes, ordem de pintura | Redações e diagramação | Há sobreposição efetiva? |
| A04 | Texto em camada opcional (OCG) | `layer`, estado de visualização | Camadas de desenho/projeto | Extração depende de estado da camada? |
| A05 | Texto fora da área visível | Bbox vs page.rect / cropbox | Marcas editoriais e pré-impressão | Texto fora do recorte aparece na extração? |
| A06 | OCR legítimo sobre digitalização | Texto invisível alinhado à imagem | Acessibilidade, busca e indexação | Como reduzir falso positivo? |

**Nota:** `get_texttrace()` pode reportar invisibilidade por Tr=3, opacidade
e indícios de sobreposição; não substitui comparação de renderização e
revisão da configuração de camadas. Não classificar conteúdo como adversarial
com base somente nesses indicadores.

## A01 — Protocolo mínimo

**Entradas:** um par de PDFs fictícios com mesmos elementos visíveis;
um contém apenas o conteúdo legítimo e outro contém marcador adicional
sem conteúdo operacional, inserido como texto não renderizado.

1. Calcular hashes SHA-256 dos originais e registrar versão do PyMuPDF.
2. Renderizar todas as páginas em configuração e resolução fixas.
3. Extrair texto com `page.get_text("text")` sem filtragem.
4. Coletar spans de `page.get_texttrace()` com página, bbox, tipo,
   opacidade, layer, seqno e fragmento de texto.
5. Obter `page.get_bboxlog(layers=True)` para cruzar ordem de pintura.
6. Comparar o conteúdo extraído, os pixels renderizados e os metadados.
7. Avaliar como um revisor humano perceberia o marcador e se alguma
   evidência legítima seria perdida por uma filtragem ingênua.

### Saídas observáveis

- `visual_parity`: renderizações equivalentes sob configuração fixada.
- `extraction_difference`: diferença em texto extraído entre as condições.
- `hidden_span_detected`: o marcador foi localizado como span não renderizado.
- `legitimate_content_preserved`: JAN/FEV/MAR e total R$ 6.000,00 ainda constam.
- `false_positive_risk`: anotação qualitativa de usos legítimos equivalentes.
- `provenance`: página, bbox, metadados e hash de fonte para cada evidência.

## Critérios de interpretação

1. **Anomalia de representação** não equivale a **instrução adversarial**.
2. **Texto invisível** não equivale a **conteúdo descartável**.
3. Detector técnico pode produzir sinal para inspeção, mas não declarar
   malícia sem contexto. Este protocolo não propõe bloqueio.
4. Registrar risco de perda de provas se um sistema remover o trecho inteiro.
5. Um teste que passa com PDFs gerados artificialmente não estabelece
   desempenho em corpus jurídico heterogêneo.

## Critérios de passagem para o próximo cenário

- Confirmar em A01 o vínculo entre diferenças extraídas e spans identificáveis.
- Demonstrar que os dados legítimos permanecem íntegros.
- Documentar ao menos um exemplo legítimo (A06) antes de projetar qualquer
  mecanismo de alerta ou descarte.
- Expandir a matriz por uma variável estrutural de cada vez.
- Só depois medir influência sobre o agente como estudo separado (Frente B).

## Fontes técnicas consultadas em 04/11/2026

- PyMuPDF: `Page.get_texttrace()` e `Page.get_bboxlog()`:
  https://pymupdf.readthedocs.io/en/latest/functions.html
- Referência Adobe PDF: modo 3 não pinta os glifos:
  https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.0.pdf
- Discussão técnica sobre camadas de OCR invisíveis:
  https://github.com/pymupdf/PyMuPDF/discussions/2505

**Próxima ação:** implementar um diagnóstico local somente-leitura para A01,
com testes offline e saídas de inspeção por página. Não consumir quota Gemini.
