# E20 — Política de decisão: autorização, contenção, revisão e falha técnica

## Objetivo

Investigar como traduzir classificações de PDFs para decisões operacionais sem
confundir uma **instrução documental sem redirecionamento** com ataque ativo.

O estudo reutiliza **as respostas históricas E18/E19**, sem novas chamadas ao
Gemini e sem executar o agente ADK. Os prompts e a política de autorização
binária existentes não são modificados.

**Decisões:**
- `allow`: autorizar automaticamente (exatamente os casos que o gate E15/E18 já autoriza);
- `contain`: classificador indica tentativa ativa de redirecionamento;
- `review`: classificação semântica contraditória ou incerta; não autoriza;
- `technical_hold`: API falhou, resposta ausente ou contrato inválido; não autoriza.

A mudança é **operacional e de auditoria**, não uma melhoria demonstrada na
taxa de autorização. A revisão humana ainda não está implementada.

Em particular, `raster_citation` da variante E18 deverá aparecer como
`review`, e não como `contain`. Isso não libera o documento automaticamente.
`registry_instruction` permanece autorizado na variante E18 e contido no
controle E15, pois seus classificadores divergem. O replay não resolve falsos
negativos coerentes.

## Windows (após merge)

```cmd
git pull origin main
.venv\Scripts\python.exe -m pytest tests/test_e20_policy_triage.py -q --basetemp=data/pytest_temp
.venv\Scripts\python.exe -m experiments.e20_policy_triage.run
```

Entrada:
- `data/executions/e18/paired.jsonl`
- `data/executions/e19/replications.jsonl`

Saída:
- `data/executions/e20/triage_report.json`

Requer históricos locais do E18 e E19, sem PDFs ou chave de API. Há opção
`--e18-only` para avaliar somente o histórico E18. A compatibilidade dos
prompts, modelos, políticas e hashes de PDF é conferida no replay.

## Limitações

- Não chamar um caso de `review` não representa melhora de disponibilidade:
  ele segue bloqueado para execução automática.
- Não há workflow de aprovação humana; não presumir que revisão sempre autoriza.
- Erros de API devem ser tratados como indisponibilidade, não como ataque.
- Gabaritos sintéticos, sem documentação jurídica real.
- Repetições E19 são observações correlacionadas; não inferir taxas populacionais.
- Classificador que falha com rótulo coerente pode autorizar ataque.
