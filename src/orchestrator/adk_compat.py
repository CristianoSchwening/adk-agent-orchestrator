"""Small compatibility helpers around optional ADK imports.

The project declares ``google-adk`` as a runtime dependency. Tests that only
validate scaffolding can run without importing ADK, while actual execution uses
lazy imports to instantiate official ADK classes.
"""

from __future__ import annotations

from importlib import import_module, metadata, util
from typing import Any

ADK_DISTRIBUTION = "google-adk"
CERTIFIED_ADK_VERSION = "2.6.1"


def is_adk_installed() -> bool:
    """Return whether the Google ADK package is importable in this environment."""

    return util.find_spec("google") is not None and util.find_spec("google.adk") is not None


def get_adk_version() -> str | None:
    """Return the installed ADK distribution version, if available."""

    try:
        return metadata.version(ADK_DISTRIBUTION)
    except metadata.PackageNotFoundError:
        return None


def ensure_certified_adk() -> str:
    """Fail fast unless the runtime uses the ADK version certified by this project."""

    installed = get_adk_version()
    if installed is None:
        raise RuntimeError(
            f"{ADK_DISTRIBUTION} is not installed; expected {CERTIFIED_ADK_VERSION}."
        )
    if installed != CERTIFIED_ADK_VERSION:
        raise RuntimeError(
            f"Unsupported {ADK_DISTRIBUTION} version {installed}; "
            f"expected {CERTIFIED_ADK_VERSION}."
        )
    return installed


def load_symbol(module_name: str, symbol_name: str) -> Any:
    """Load an ADK symbol lazily.

    Lazy loading keeps module import side effects small and lets unit tests
    exercise configuration/policy code even when the ADK wheel is not installed
    in the current interpreter.
    """

    module = import_module(module_name)
    return getattr(module, symbol_name)


def load_agent_class() -> Any:
    """Load Agent from the public top-level ADK API."""

    return load_symbol("google.adk", "Agent")


def load_workflow_agent_classes() -> tuple[Any, Any, Any]:
    """Load the public classic workflow-agent exports."""

    module = import_module("google.adk.agents")
    return module.SequentialAgent, module.ParallelAgent, module.LoopAgent


def load_runtime_classes() -> tuple[Any, Any, Any, Any]:
    """Load App, Runner and the public in-memory service exports."""

    App = load_symbol("google.adk.apps", "App")
    Runner = load_symbol("google.adk", "Runner")
    InMemorySessionService = load_symbol("google.adk.sessions", "InMemorySessionService")
    InMemoryArtifactService = load_symbol("google.adk.artifacts", "InMemoryArtifactService")
    return App, Runner, InMemorySessionService, InMemoryArtifactService


def load_content_classes() -> tuple[Any, Any]:
    """Load Google Gen AI content types used at the runner boundary."""

    module = import_module("google.genai.types")
    return module.Content, module.Part


def load_mcp_classes() -> tuple[Any, Any, Any, Any, Any]:
    """Load MCP symbols from the ADK package's public MCP export module."""

    module = import_module("google.adk.tools.mcp_tool")
    mcp_module = import_module("mcp")
    return (
        module.McpToolset,
        mcp_module.StdioServerParameters,
        module.StdioConnectionParams,
        module.SseConnectionParams,
        module.StreamableHTTPConnectionParams,
    )
