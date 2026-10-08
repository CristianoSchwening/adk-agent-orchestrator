# Kev via MCP no Hugging Face

O servidor `https://jaredpalmer-kev.hf.space/gradio_api/mcp/` usa Streamable HTTP
e expõe `kev_decide`. Não precisa instalar Gradio, PyTorch ou pesos locais:
o SDK MCP já vem com a dependência ADK deste projeto.

Copie a configuração `ADK_MCP_SERVERS` de `.env.example` para `.env`, preservando
outros servidores. A entrada deve ter `name=kev` e `transport=streamable_http`.
O campo `bearer_token_env` indica a variável local que contém o token opcional.
Não coloque tokens no JSON de servidores ou em arquivos versionados.

No PowerShell, na raiz do projeto:

```powershell
.venv/Scripts/python.exe -m orchestrator.mcp.kev
.venv/Scripts/python.exe -m orchestrator.mcp.kev --smoke
```

O primeiro comando inicializa a sessão e lista ferramentas, sem inferência.
O segundo envia uma tarefa fictícia e consome a cota ZeroGPU. O retorno normaliza
o envelope textual Gradio, descarta HTML e valida opções, probabilidades e confiança.
O schema remoto de `n_perm` declara string com enum numérico e rejeita o valor 4;
o cliente omite esse parâmetro opcional e usa o padrão do Space. O teste de
permutação fica desativado para poupar cota.

O acesso anônimo pode permitir descoberta e ainda recusar inferência por cota.
Se necessário, configure `HF_TOKEN` localmente com as permissões mínimas exigidas
pelo Hugging Face. Login no navegador não autentica o processo Python. Nunca
cole o token em chats. Não há repetição automática de chamadas.

## Observação no ADK

`ADK_KEV_SHADOW_ENABLED=false` é o padrão: nenhuma tarefa real sai automaticamente.
Para experimentar com tarefas públicas/sintéticas, mude para `true` e reinicie o
servidor. O FunctionNode do dispatcher chama o MCP antes de executar cada tarefa,
enviando somente título, descrição e capacidades. Esses campos ainda podem conter
dados confidenciais: use apenas conteúdo adequado ao Space público.

O agente escolhido pelo dispatcher não é alterado. A sessão registra as respostas
em `kev_shadow_observations`, junto com a escolha local para comparação. Esses
registros também aparecem em `metrics.custom.kev_shadow_observations` na resposta
de `/api/run` e em `tasks[].kev_observation` nos arquivos `data/task_runs/RUN-*.json`.
`status=observed` confirma resposta validada; `unavailable` indica falha, com
`error_type`; lista vazia significa que nenhuma observação foi registrada.
Ainda não existe visualização dedicada na SPA. O modo demo não chama o Kev.
Falhas e timeout registram `unavailable` e a execução continua normalmente.
Cada consulta tem limite de 60 segundos, sem retries; filas e limites do serviço
podem impedir a inferência. Desative a opção para não acrescentar essa espera.

O token também é resolvido pela factory ADK `create_configured_mcp_toolsets`.
O fluxo de observação usa uma sessão MCP explícita dentro do FunctionNode para
controlar o payload, fechar conexões e não delegar essa chamada ao LLM.

Validação remota em 2026-10-07: inicialização e descoberta funcionaram; o smoke
retornou `researcher_agent`, probabilidade 0.7854, confidence 0.7317 e 1145.4 ms
de tempo do modelo. Confiança e probabilidade não são o mesmo campo. O tempo
total também inclui rede, inicialização e fila. Esse único exemplo não é benchmark.
