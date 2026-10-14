# Migração ADK 2.8.0 → 2.11.0 — etapas 1–4

Validação realizada em 14 de outubro de 2026, Windows, Python 3.12.14.

## Etapa 1: referência

Ambiente original `.venv`, com google-adk 2.8.0:

```powershell
.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-adk280-baseline-unrestricted
```

Resultado: **207 passed, 9 warnings in 44.11s**, nenhuma falha.
Os avisos referem-se ao TestClient/HTTPX, BaseAgentConfig e recursos experimentais.
A primeira tentativa no sandbox ficou bloqueada e foi interrompida; a execução
completa foi realizada fora do sandbox. Ruff também passou.

## Etapa 2: dependências e inicialização

Atualizados o pin em `pyproject.toml`, a versão aceita pelo runtime, os testes
de versão, o README e os quatro arquivos de constraints da CI.
As demais versões transitivas foram preservadas: a resolução com ADK 2.11.0
não exigiu mudanças adicionais. MCP permanece em **1.29.0**, sem ativar o
caminho opt-in do SDK 2.x.

Foi criado um ambiente separado, mantendo `.venv` em 2.8.0 para comparação:

```powershell
.venv/Scripts/python.exe -m venv .venv-adk211
.venv-adk211/Scripts/python.exe -m pip install -c constraints-3.12.txt -e '.[dev]'
.venv-adk211/Scripts/python.exe -m pip check
.venv-adk211/Scripts/python.exe -m pytest -q --basetemp=.pytest-adk211-validation
.venv-adk211/Scripts/python.exe -m ruff check src tests
```

Resultados: instalação limpa concluída; `pip check` sem conflitos;
**207 passed, 3 warnings in 21.14s**; Ruff aprovado.
Os testes existentes cobrem construção de App/Runner, serviços de sessão e
artefatos, trajetória determinística e configuração dos três transportes MCP
sem conexão externa. Não foram feitas chamadas a modelos ou servidores MCP reais.

Também passou a resolução simulada com pip para Python 3.10, 3.11 e 3.13,
usando os respectivos constraints e `--dry-run --ignore-installed
--only-binary=:all: --python-version`. Essas verificações usam wheels Windows;
a matriz Linux completa continua sendo responsabilidade da CI.

## Etapa 3: compatibilidade

Revisados os arquivos do wheel instalado de ADK 2.11.0:

- `StaleSessionError` e `RequestInput` possuem exports públicos. O projeto
  passou a usá-los.
- `NodeInterruptedError` continua interno e deriva de `BaseException`, para
  não ser capturado pelo tratamento comum de falhas. Seu carregamento foi
  concentrado em `adk_compat.py`; o dispatcher captura apenas esse sinal e
  propaga a interrupção, preservando o estado `awaiting_human`.
- `DynamicNodeFailError` conserva `error` e `error_node_path`. O diagnóstico
  continua extraindo a causa sem depender de um import interno em produção.
- `_storage_update_marker` continua sendo um datetime ISO privado. O acesso
  foi concentrado na camada de compatibilidade. A recuperação agora exige
  o mesmo instante UTC e a mesma sequência de IDs de eventos; não basta
  possuir o mesmo conjunto de IDs. Marcadores ausentes ou inválidos não
  autorizam uma nova tentativa. O segundo append mantém a verificação de
  concorrência do ADK.
- Contratos de serialização de `RequestInput`, `Event` e `EventActions`
  foram validados, incluindo aliases, saída, rota, delta e invocation ID.

Novas regressões SQLite demonstram recuperação de uma diferença de timezone
do mesmo instante e rejeição de uma revisão diferente com histórico idêntico.
O teste existente de escritor concorrente obsoleto continua passando.

```powershell
.venv-adk211/Scripts/python.exe -m pytest -q tests/test_human_interaction.py tests/test_adk_runtime_integration.py --basetemp=.pytest-adk211-stage3
.venv-adk211/Scripts/python.exe -m pytest -q --basetemp=.pytest-adk211-stage3-full
```

Os testes específicos passaram: **20 passed, 3 warnings**. A suíte completa
passou: **210 passed, 3 warnings in 37.01s**. Ruff aprovado.

## Etapa 4: aprovação humana e reinício

Os cenários de aprovação, rejeição, revisão e esclarecimento agora rodam
também em processos Python distintos. Cada chamada inicia um novo processo,
reconstrói App/Runner e lê o mesmo snapshot e banco SQLite. Os nós são
determinísticos; nenhum modelo ou serviço externo é chamado.

Verificações:

- Mesma sessão, execução, tarefa, data de criação, invocation ID e tentativa.
- Resposta idêntica repetida retorna o resultado salvo; resposta com comentário
  ou chave diferente recebe 409, sem nova execução.
- Rejeição encerra sem executar a continuação; revisão e esclarecimento criam
  uma nova solicitação, que exige aprovação da nova proposta.
- Preparação já concluída não se repete; a continuação aprovada roda uma vez.
- Cada resposta humana aparece uma única vez nos eventos persistidos do ADK.
- Falha simulada após salvar a decisão, antes da continuação, permite retomar
  a mesma resposta em outro processo e rejeita respostas conflitantes.
- Falha simulada após salvar o contrato da continuação, antes de confirmar o
  recibo, permite recuperar o resultado em outro processo sem rodar novamente.

O último cenário revelou um 409 indevido: a solicitação já estava respondida,
mas o recibo ainda não estava concluído. O endpoint agora reconhece a decisão
humana idêntica no contrato persistido, valida usuário e sessão, conclui o
recibo sob o lock da execução e devolve o resultado salvo. O ajuste cobre
também rejeição e fluxos que pausam novamente para revisão/esclarecimento.

```powershell
.venv-adk211/Scripts/python.exe -m pytest -q --basetemp=.pytest-adk211-stage4-full
.venv-adk211/Scripts/python.exe -m pytest -q tests/test_human_interaction.py::test_human_response_survives_real_process_restart --basetemp=.pytest-adk211-stage4-event-count
```

As interrupções nos pontos de persistência são injetadas deterministicamente;
os reinícios usam processos reais. Isso não certifica ainda uma falha arbitrária
durante uma ação externa do dispatcher, que pertence à etapa 5.

Resultados: **218 passed, 3 warnings in 212.61s** na suíte completa;
**4 passed, 1 warning in 108.32s** na conferência adicional dos eventos SQLite.
Ruff e verificação de whitespace aprovados. A execução foi em Windows / Python
3.12.14 com ADK 2.11.0; a matriz Linux continua a cargo da CI.

## Etapas 5–6

A auditoria não conclui a retomada após falha com efeitos externos ou
a prevenção de ações duplicadas. Essas verificações permanecem nas etapas
5–6 do plano. Fallback nativo, novas métricas, cancelamento e memória SQLite
não foram adotados nesta alteração.

O alvo continua sendo 2.11.0, embora o índice já ofereça 2.12.0 nesta data.
Antes de ativar a atualização em um ambiente persistente, preservar a base
de sessões e concluir os critérios de retomada/idempotência. A reversão do
código e dos constraints deve acompanhar a restauração do ambiente 2.8.0;
compatibilidade de dados gravados por 2.11.0 ainda não foi certificada.
