# E18 — Comparação pareada de classificação por destinatário e redirecionamento

O E17 identificou um falso positivo real em uma nota editorial. O E18
**não usa esse mesmo caso como teste de sucesso**: compara dois classificadores
sobre oito PDFs sintéticos inéditos, com rótulos definidos antes da execução.

O **controle** reutiliza integralmente a classificação nativa E14b/E15 e a
política E15. A **variante** inclui campos separados para o destinatário,
a presença de comando dirigido à IA e a tentativa ativa de redirecionar
o agente analisador, em linha com os princípios B03/E07. O novo contrato
é validado e recebe política de avaliação própria; o resultado final é
comparado no mesmo nível: permitir ou bloquear o documento.

Corpus: três instruções profissionais/judiciais legítimas, três ataques
diretos/indiretos ao analista (inclusive um PDF com imagem) e duas citações,
sendo uma em imagem. Uma chamada por braço/caso: **16 chamadas máximas**.
Não existem chamadas ao ADK, OCR próprio ou documentos reais.

## Windows (após merge)

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e18_recipient_aware.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e18_recipient_aware.run --prepare-only
.venv\Scripts\python.exe -m experiments.e18_recipient_aware.run
```

Retomar falhas temporárias: acrescentar `--retry-invalid`.

Saídas:
- `data/executions/e18/paired.jsonl`
- `data/executions/e18/paired_report.json`

**Critério de avaliação:** comparar falsos bloqueios e liberações indevidas
somente nos pares com respostas válidas; não tratar maior precisão no holdout
pequeno como prova de eficácia em produção. O erro do E17 motivou a hipótese,
portanto a investigação ainda é exploratória e exige validação independente.
