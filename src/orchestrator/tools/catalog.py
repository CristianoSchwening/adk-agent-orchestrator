"""Catalog of current and planned tools for the ADK orchestrator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ToolCategory = Literal["filesystem", "http", "documents", "data", "model", "mcp", "core"]
ToolAvailability = Literal["available", "planned", "external"]


@dataclass(frozen=True)
class ToolDefinition:
    """Serializable metadata for one tool capability."""

    name: str
    category: ToolCategory
    availability: ToolAvailability
    description: str
    safe_by_default: bool = True


TOOL_CATALOG: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="capture_objective",
        category="core",
        availability="available",
        description="Captures the user objective as structured session metadata.",
    ),
    ToolDefinition(
        name="get_orchestrator_status",
        category="core",
        availability="available",
        description="Reports the current ADK phase and orchestrator capabilities.",
    ),
    ToolDefinition(
        name="request_human_approval",
        category="core",
        availability="available",
        description="Records an explicit human approval decision for HITL workflows.",
    ),
    ToolDefinition(
        name="list_available_tools",
        category="core",
        availability="available",
        description="Lists the Phase 3 tool catalog by category and availability.",
    ),
    ToolDefinition(
        name="get_tool_usage_metrics",
        category="core",
        availability="available",
        description="Returns process-local tool usage events and metrics.",
    ),
    ToolDefinition(
        name="read_text_file",
        category="filesystem",
        availability="available",
        description="Reads a bounded UTF-8 text file from the current workspace.",
    ),
    ToolDefinition(
        name="fetch_http_text",
        category="http",
        availability="available",
        description="Fetches bounded text from an HTTP/HTTPS URL with a timeout.",
    ),
    ToolDefinition(
        name="extract_document_outline",
        category="documents",
        availability="available",
        description="Extracts markdown-style headings and basic document statistics.",
    ),
    ToolDefinition(
        name="inspect_json_records",
        category="data",
        availability="available",
        description="Inspects JSON arrays/objects and reports schema-like summary data.",
    ),
    ToolDefinition(
        name="describe_model_request",
        category="model",
        availability="available",
        description="Builds a safe model-call plan without invoking a model directly.",
    ),
    ToolDefinition(
        name="create_configured_mcp_toolsets",
        category="mcp",
        availability="external",
        description="Creates ADK MCPToolset instances from ADK_MCP_SERVERS configuration.",
    ),
    ToolDefinition(
        name="filesystem_mcp_toolset",
        category="filesystem",
        availability="planned",
        description="External MCP server for richer filesystem operations.",
    ),
    ToolDefinition(
        name="documents_mcp_toolset",
        category="documents",
        availability="planned",
        description="External MCP server for document conversion, parsing and indexing.",
    ),
    ToolDefinition(
        name="data_mcp_toolset",
        category="data",
        availability="planned",
        description="External MCP server for databases, warehouses and tabular analysis.",
    ),
)


def list_available_tools(category: ToolCategory | None = None) -> dict[str, object]:
    """Return the tool catalog, optionally filtered by category."""

    definitions = [tool for tool in TOOL_CATALOG if category is None or tool.category == category]
    return {
        "status": "success",
        "phase": "phase_3_tools_mcp",
        "count": len(definitions),
        "tools": [asdict(tool) for tool in definitions],
    }
