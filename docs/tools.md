# Fase 3 — Tools e MCP

A Fase 3 adiciona uma camada inicial de ferramentas ao backend ADK Python. A orquestração continua no backend; Android, Web ou CLI devem atuar apenas como clientes.

## Objetivos

- Catalogar ferramentas atuais e desejadas por categoria.
- Expor ferramentas locais simples como ADK function tools.
- Preparar integração com ferramentas externas via ADK `MCPToolset`.
- Padronizar timeout e payloads de erro.
- Registrar uso de ferramentas em eventos/métricas locais.

## Catálogo de ferramentas

O catálogo fica em `src/orchestrator/tools/catalog.py` e cobre:

| Categoria | Exemplos |
| --- | --- |
| `core` | `capture_objective`, `get_orchestrator_status`, `request_human_approval`, métricas |
| `filesystem` | `read_text_file`, MCP filesystem planejado |
| `http` | `fetch_http_text` |
| `documents` | `extract_document_outline`, MCP documents planejado |
| `data` | `inspect_json_records`, MCP data planejado |
| `model` | `describe_model_request` |
| `mcp` | factory de `MCPToolset` |

A tool `list_available_tools` retorna esse catálogo de forma estruturada para o agente raiz.

## Tools locais

As tools locais em `src/orchestrator/tools/local.py` são seguras por padrão:

- `read_text_file`: lê arquivos UTF-8 limitados ao workspace atual.
- `fetch_http_text`: busca texto HTTP/HTTPS com limite de bytes e timeout.
- `extract_document_outline`: extrai headings markdown e estatísticas básicas.
- `inspect_json_records`: sumariza campos e tipos de JSON objects/arrays.
- `describe_model_request`: descreve uma chamada de modelo sem executá-la.

Todas usam `execute_tool_call`, que aplica timeout, captura exceções e retorna payloads padronizados:

```json
{
  "status": "success",
  "tool_name": "read_text_file",
  "elapsed_ms": 3,
  "data": {}
}
```

ou:

```json
{
  "status": "error",
  "tool_name": "read_text_file",
  "elapsed_ms": 1,
  "error": {"code": "FileNotFoundError", "message": "File not found: missing.txt"},
  "data": {}
}
```

## Timeouts

Configure o timeout padrão das tools locais com:

```bash
ADK_TOOL_TIMEOUT_SECONDS="10"
```

Esse valor é lido por `OrchestratorSettings.from_env()`.

## MCP

A integração MCP fica em `src/orchestrator/mcp/factory.py`. Ela é lazy: o projeto pode importar normalmente sem instalar extras MCP, e os imports de `MCPToolset` só acontecem quando `create_configured_mcp_toolsets` é chamado.

Configure servidores externos via JSON:

```bash
ADK_MCP_SERVERS='[
  {
    "name": "filesystem",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
  }
]'
```

Transportes suportados na configuração:

- `stdio`
- `sse`
- `streamable_http`

Use `describe_mcp_servers` para inspecionar a configuração sem abrir subprocessos ou conexões.

## Métricas

`src/orchestrator/tools/metrics.py` mantém métricas process-local para esta fase:

- chamadas por ferramenta;
- sucessos;
- erros;
- timeouts;
- tempo total e médio;
- eventos estruturados com timestamps.

Ferramentas expostas:

- `get_tool_usage_metrics`
- `reset_tool_usage_metrics`

Em fases posteriores, esses eventos devem ser mapeados para ADK Session Events, contrato UI/API e observabilidade de produção.
