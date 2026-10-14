# Migração ADK 2.8.0 → 2.11.0 — etapas 1 e 2

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

## Próximas etapas

A aprovação da suíte existente não conclui a auditoria dos imports internos,
do marcador privado de sessão, da retomada após falha com efeitos externos ou
da prevenção de ações duplicadas. Essas verificações permanecem nas etapas
3–6 do plano. Fallback nativo, novas métricas, cancelamento e memória SQLite
não foram adotados nesta alteração.

O alvo continua sendo 2.11.0, embora o índice já ofereça 2.12.0 nesta data.
Antes de ativar a atualização em um ambiente persistente, preservar a base
de sessões e concluir os critérios de retomada/idempotência. A reversão do
código e dos constraints deve acompanhar a restauração do ambiente 2.8.0;
compatibilidade de dados gravados por 2.11.0 ainda não foi certificada.
