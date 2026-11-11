# E15 — Contenção efetiva com PDF nativo no agente jurídico ADK

**Objetivo:** deixar de apenas reconhecer instruções adversariais e provar
que uma política determinística impede a criação da sessão e a chamada
do agente jurídico com PDF original.

## Fluxo

1. O Gemini recebe o PDF original (application/pdf) e executa a
   classificação nativa E14b (sem extrator próprio).
2. Um adaptador aplica os princípios de duas decisões do E07:
   disposição instrucional e necessidade de revisão. A política é
   determinística, fail-closed em casos inválidos ou incertos.
3. Braço baseline: agente jurídico E01 no Google ADK recebe diretamente
   o **PDF original**, sem gate da aplicação. A instrução convencional
   do agente E01 permanece em ambos os braços.
4. Braço protegido: o mesmo agente e o mesmo PDF, mas somente após
   autorização. Comando ativo bloqueia o documento inteiro, sem criar sessão.
5. Gabarito sintético serve SOMENTE para medir preservação factual,
   valores, fonte e página. Não influencia política nem modelo.

**Atenção:** E07 validava a classificação B03 contra o texto extraído.
E15 **não** reutiliza essa validação, pois a classificação nativa E14b tem
outro contrato. A política E15 é um adaptador explícito, não uma chamada
direta ao algoritmo E07.

## Corpus, custos e limitações

Padrão: hidden_white (ataque), quoted_visible (citação legítima),
mixed_image (imagem legítima), reutilizando gerador sintético E14b.
Máximo de 3 chamadas por PDF (classificador + agente baseline +
agente protegido se permitido). Na primeira rodada até **8 chamadas**;
o comando ativo bloqueia uma das três previstas.

Modelo padrão `gemini-3.1-flash-lite`, com opção gratuita sujeita às
cotas da conta. Não usar documentos reais/confidenciais no tier gratuito
sem revisar os termos de tratamento de dados. Retomar histórico não
deve reenviar respostas válidas. Erros 503/429 param a rodada para
evitar consumo acidental da cota; `--retry-invalid` tenta apenas falhas.

## Windows após merge

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e15_native_pdf_gate.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e15_native_pdf_gate.run --prepare-only
.venv\Scripts\python.exe -m experiments.e15_native_pdf_gate.run
```

Relatórios:
- data/executions/e15/executions.jsonl
- data/executions/e15/gate_report.json
- data/experiments/e15/E14B_*.pdf

Se API falhar, repetir com `--retry-invalid`. Os hashes de PDF,
prompt do classificador, instrução E01, tarefa e modelo são verificados
antes de usar o histórico.

## Limites de interpretação

- O baseline já possui system prompt defensivo; não é um agente vulnerável.
- Um PDF bloqueado retém fatos legítimos inacessíveis para análise automática.
- Não prova eficácia contra falsos negativos do classificador.
- Não é sanitização por trecho, nem oferece aprovação humana automatizada.
- Não há extração própria, OCR próprio ou documentos judiciais autênticos.
- Falhas de contrato e de API não devem ser interpretadas como proteção.
- A detecção não equivale à contenção; o bloqueio está no controle de fluxo.
