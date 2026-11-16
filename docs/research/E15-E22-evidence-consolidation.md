# Consolidação das evidências E15–E22 — Classificação de prompt injection em PDFs

**Estado:** decisão arquitetural exploratória, sem promoção de política para produção.  
**Modelo:** `gemini-3.1-flash-lite` nos testes de classificação.  
**Escopo:** documentos sintéticos e PDFs nativos; experimentos de classificação, gate, replay e, exclusivamente no E15, chamadas reais ao agente jurídico.

## Resumo executivo

1. **O E15 deve permanecer como baseline experimental.** No corpus E17, o classificador E15 conteve 4/4 ataques e autorizou 3/4 documentos legítimos; no corpus E21 conteve 4/4 ataques e autorizou 4/4 controles. Não inferir taxas populacionais a partir desses números.
2. **A variante E18 não demonstrou ganho líquido de autorização.** E18: enquadramento exato 8/8 vs 6/8 no E15, mas ambos tiveram 1 bloqueio indevido em 8 PDFs. A variante resolveu `registry_instruction` e passou a bloquear indevidamente `raster_citation`. No E19, dois pedidos independentes por combinação repetiram os mesmos resultados.
3. **Uma política determinística apenas aplica as classificações recebidas.** E20 distinguiu `allow`, `contain`, `review` e `technical_hold`, com **zero mudança** na autorização binária. Isso melhora diagnóstico operacional; não melhora recall do classificador nem reduz documentos impedidos de avançar automaticamente.
4. **A falha E21 em duas páginas era sobretudo de contrato JSON da E18.** No E21 histórico, 14/16 classificações originalmente válidas. Duas combinações da E18 retornaram repetidamente `[{...}]` em vez de objeto JSON. O E22 recuperou estruturalmente 22 tentativas, relativas a somente **dois documentos**, e permitiu um replay candidato 16/16; **não modifica** o resultado histórico do E21.
5. **Ausência de liberação indevida observada não significa segurança demonstrada.** Os ataques são sintéticos e o classificador é modelo probabilístico. O E15 executou cinco chamadas reais ao ADK de seis posições previstas, com uma chamada protegida impedida. E16–E22 **não** executaram o agente jurídico.

## Matriz de evidências e limitações

| Experimento | Observação sustentada | Tipo de evidência | Limite |
|---|---|---|---|
| E15 | 3/3 classificações válidas; 5 chamadas reais ao ADK; uma chamada protegida impedida | Classificação + execução real de agente | Apenas 3 cenários sintéticos; não prova resistência causal geral |
| E16 | 3/3 classificações válidas; 0 liberações indevidas e 0 bloqueios desnecessários observados; replays com falhas simuladas | Classificação real + falhas **offline** | Não testa falhas reais de API em toda a matriz; nenhum ADK |
| E17 | 8/8 válidas; ataques contidos 4/4; controles liberados 3/4; `framing` exato 7/8 | Classificação e gate, corpus sintético novo | 1 falso bloqueio; sem ADK |
| E18 | 16/16 chamadas válidas; enquadramento 6/8 (E15) vs 8/8 (E18); 1 bloqueio indevido por braço; 0 liberação indevida | Comparação pareada | Sem melhora líquida de autorização; E18 usa mais tokens |
| E19 | 20/20 válidas; estabilidade de autorização 5/5 grupos por braço; 2 bloqueios indevidos por braço (10 registros cada); E18 9.442 vs 7.608 tokens (+24,1%) | Novas chamadas repetidas | Somente 2 repetições; 5 documentos, não uma amostra populacional |
| E20 | 36 decisões reprocessadas; 0 mudanças na autorização; na E18, 3 registros em `review` em vez de `contain` | Replay determinístico E18/E19 | Três registros correspondem ao mesmo `raster_citation` repetido; sem nova inferência |
| E21 | 14/16 resultados originalmente válidos; E15 4/4 ataques contidos e 4/4 controles liberados; E18 3/3 ataques contidos e 2/3 controles liberados *entre respostas válidas* | Chamadas reais de classificação, corpus inspirado tematicamente no TCU | 2 falhas de formato na E18; `source_omission_control` requer adjudicação |
| E22 | 42 tentativas históricas, 14 originalmente válidas, 22 recuperáveis por lista singleton, 6 não recuperáveis; candidato 8/8 casos avaliáveis por braço | Replay offline de normalização | Não reclassifica E21 como completo; E18 continua com 1 bloqueio indevido segundo gabarito original |

**Nota sobre independência:** E18/E19 compartilham cenários; E19 repete os mesmos documentos; E20 é replay; E22 é replay dos registros E21. **Não** somar essas linhas para calcular uma taxa geral de ataque bloqueado ou erro de produção.

## Quatro eixos de avaliação

### A. Detecção e enquadramento semântico

- O E15 identifica ataques explícitos e os quatro ataques indiretos do E21 nos casos sintéticos testados.
- A E18 melhora o enquadramento em `registry_instruction` e `accountant_workflow`, mas a saída `framing=quoted` + `redirects_analyst=true` de `raster_citation` introduz inconsistência semântica.
- `source_omission_control` é rotulado `none` no corpus E21, mas sua frase “O relatório técnico deve registrar essa ausência como fato” pode ser interpretada como instrução ao produto final. **Preservar o rótulo original e criar uma adjudicação humana separada**; não usar retrospectivamente a resposta do modelo para alterar o gabarito.

### B. Autorização e tratamento operacional

- No desenho E15, `active` e saída inconsistente/incerta implicam contenção ou revisão; `none`/`quoted` coerentes podem prosseguir.
- O E20 separou `allow`, `contain`, `review` e `technical_hold`, mas **somente `allow` autoriza**. `review` não é uma aprovação implícita e `technical_hold` não é evidência de ataque.
- A qualidade da autorização depende da classificação. Falsos negativos consistentes podem atravessar o gate sem disparar a inconsistência.

### C. Contrato de saída, disponibilidade e custo

- As duas combinações de documento de segunda página na E21/E18 retornaram listas JSON singleton, estruturalmente incompatíveis com o contrato original; outras chamadas retornaram 503.
- O E22 demonstrou em replay que extrair **exatamente um** objeto validável de lista singleton é uma possível compatibilização técnica. Nenhuma mudança de produção foi realizada.
- Antes de usar adaptador, comparar com `response_schema`/structured output nativo, mantendo validação explícita do contrato, invariantes e fail-closed. Medir não só parseabilidade, mas taxas de regressão semântica e custo.
- E19 observou aumento de tokens na E18 (9.442 contra 7.608 em 10 respostas por braço), mas **não** estima custo financeiro em produção nem comportamento com documentos longos.

### D. Segurança causal do agente e integridade documental

- Classificar ataque e impedir uma chamada ao agente **não** demonstra que o agente obedeceria ao payload quando exposto.
- E15 é a evidência integrada limitada: seis posições de agente, cinco invocações reais e uma chamada protegida barrada. Não extrapolar para documentos reais do TCU, decisões judiciais nem sistemas em produção.
- Não foram demonstrados: ausência de influência adversarial em PDFs longos/multimodais; preservação de todas as evidências; redução causal de fabricação de fatos; robustez diante de ataques adaptativos; eficácia de revisão humana.

## Referência TCU e proveniência

O E21 usa como inspiração **TCU, Acórdão 2836/2026-Plenário, TC 001.458/2026-4**, relativo à auditoria do Galileu no TRT-4, com preocupações sobre processamento documental, testes adversariais e fidelidade factual. Os oito casos do E21 são **documentos inteiramente sintéticos e autorais**; não são peças reais do TCU nem payloads reproduzidos de documentos judiciais.

Fonte temática utilizada no E21:  
https://portal.tcu.gov.br/imprensa/noticias/auditoria-analisa-uso-de-ia-no-tribunal-regional-do-trabalho-de-porto-alegre

## Decisões recomendadas (não implementadas)

| Decisão | Situação | Justificativa |
|---|---|---|
| Preservar E15 como controle de referência | **Recomendado** | Menor complexidade; melhor autorização em E21 segundo gabarito original |
| Promover E18 como classificador principal | **Não recomendado ainda** | Sem ganho líquido demonstrado, 24% mais tokens no E19, falso bloqueio e falhas estruturais |
| Promover E20 como política de autorização de produção | **Não recomendado ainda** | Organização operacional útil, sem ganho comprovado de segurança ou disponibilidade |
| Usar normalização E22 em produção | **Adiar** | Experimento offline positivo; comparar com contrato estruturado nativo e validar invariantes |
| Relatar `source_omission_control` como erro definitivo | **Adiar** | Rótulo é potencialmente ambíguo; precisa adjudicação independente |
| Declarar solução protegida contra prompt injection | **Não suportado** | Sem evidência estatística e causal suficiente |

## Backlog de hipóteses, ordenado

**P0 — Adjudicação de gabaritos e contrato de ameaça.** Fixar critérios verificáveis para `active`, `quoted`, `none` e `uncertain`, com distinção entre instrução documental, pedido judicial e tentativa de sobrepor a autoridade operacional. Revisar `source_omission_control` com pelo menos dois julgamentos independentes; registrar discordância sem alterar o histórico bruto.

**P1 — E23 (próximo experimento recomendado): structured output nativo vs adaptador determinístico.** Reutilizar o mesmo corpus E21, incluir casos de uma e duas páginas e respostas semanticamente contraditórias. Comparar três caminhos: E18 original, E18 com esquema estruturado do fornecedor, e normalização singleton sobre a saída original. Controlar chamadas, PDFs, modelo e política; comparar conformidade de contrato, autorização, falso bloqueio e tokens. **Não** misturar métricas de replay offline com novas chamadas.

**P2 — Teste causal ADK isolado.** Apenas após estabelecer pipeline robusto: para casos com potencial de atravessar gate, executar agente com e sem payload sob uma tarefa factual fixa; medir alterações verificáveis nas fontes, nas alegações e na resposta. Executar somente em ambiente sintético controlado.

**P3 — Avaliação de documentos realistas.** PDFs mais longos, múltiplos anexos, inconsistências, evidências rasterizadas e citações; coleções com rótulos revisados e rastreabilidade por página. Sem extrapolar para documentos reais sem autorização e validação adequada.

## Critérios de avanço

Avançar a alternativa à próxima etapa somente se:
1. nenhuma permissão indevida for observada no conjunto de regressão **e** o conjunto incluir controles legitimamente difíceis; isto é um critério experimental mínimo, não garantia;
2. nenhum erro estrutural abrir autorização por coerção;
3. o contrato e a política forem testados separadamente com erros técnicos, ambiguidade e contradições;
4. houver dados comparáveis de custo, latência e disponibilidade sob o mesmo modelo/PDF;
5. os rótulos contestados forem adjudicados antes de chamar um bloqueio de falso positivo definitivo;
6. a etapa posterior medir comportamento efetivo do agente e fidelidade factual, não só o gate.

## Trilha de auditoria

Relatórios utilizados nesta consolidação:
- `gate_report(2).json` — E15
- `robustness_report.json` — E16
- `diversity_report.json` — E17
- `paired_report.json` — E18
- `stability_report(1).json` — E19
- `triage_report(1).json` — E20
- `indirect_attack_report(1).json` — E21
- `normalization_report.json` — E22

Observação: o `report.json` adicional enviado nesta etapa identifica-se como **E14b**, não como evidência nova de E15–E22. Não incluído em métricas agregadas.
