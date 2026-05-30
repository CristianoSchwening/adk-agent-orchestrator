"""Factory helpers for ADK MCPToolset integrations."""

from __future__ import annotations

from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.config import MCPServerSettings, OrchestratorSettings


def describe_mcp_servers(settings: OrchestratorSettings | None = None) -> dict[str, Any]:
    """Return configured MCP servers without opening network or subprocess connections."""

    resolved_settings = settings or OrchestratorSettings.from_env()
    return {
        "status": "configured" if resolved_settings.mcp_servers else "not_configured",
        "count": len(resolved_settings.mcp_servers),
        "servers": [
            {
                "name": server.name,
                "transport": server.transport,
                "command": server.command,
                "args": list(server.args),
                "url": server.url,
                "env_keys": sorted(server.env),
            }
            for server in resolved_settings.mcp_servers
        ],
    }


def _connection_params_for(server: MCPServerSettings) -> Any:
    """Create ADK MCP connection params for one server configuration."""

    if server.transport == "stdio":
        if not server.command:
            raise ValueError(f"MCP stdio server {server.name!r} requires command.")
        StdioConnectionParams = load_symbol(
            "google.adk.tools.mcp_tool.mcp_session_manager",
            "StdioConnectionParams",
        )
        return StdioConnectionParams(command=server.command, args=list(server.args), env=server.env)

    if server.transport == "sse":
        if not server.url:
            raise ValueError(f"MCP sse server {server.name!r} requires url.")
        SseConnectionParams = load_symbol(
            "google.adk.tools.mcp_tool.mcp_session_manager",
            "SseConnectionParams",
        )
        return SseConnectionParams(url=server.url)

    if not server.url:
        raise ValueError(f"MCP streamable_http server {server.name!r} requires url.")
    StreamableHTTPConnectionParams = load_symbol(
        "google.adk.tools.mcp_tool.mcp_session_manager",
        "StreamableHTTPConnectionParams",
    )
    return StreamableHTTPConnectionParams(url=server.url)


def create_configured_mcp_toolsets(settings: OrchestratorSettings | None = None) -> list[Any]:
    """Create ADK MCPToolset instances for all configured MCP servers.

    This function is lazy and optional: importing the project does not require
    the MCP extra packages. If MCP dependencies are missing, callers receive the
    underlying import error when they explicitly opt into MCP toolset creation.
    """

    resolved_settings = settings or OrchestratorSettings.from_env()
    MCPToolset = load_symbol("google.adk.tools.mcp_tool.mcp_toolset", "MCPToolset")
    return [
        MCPToolset(connection_params=_connection_params_for(server))
        for server in resolved_settings.mcp_servers
    ]
