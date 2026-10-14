"""Small compatibility helpers around optional ADK imports.

The project declares ``google-adk`` as a runtime dependency. Tests that only
validate scaffolding can run without importing ADK, while actual execution uses
lazy imports to instantiate official ADK classes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module, metadata, util
from typing import Any

ADK_DISTRIBUTION = "google-adk"
CERTIFIED_ADK_VERSION = "2.11.0"


def load_node_interrupted_error() -> type[BaseException]:
    """ADK 2.11 has no public export for the dynamic-node HITL signal.

    Keep this version-sensitive dependency here; never catch all BaseExceptions
    in the dispatcher, since cancellation must propagate independently.
    """
    return load_symbol("google.adk.workflow._errors", "NodeInterruptedError")


def sync_equivalent_session_revision(session: Any, fresh: Any) -> bool:
    """Repair only SQLite timezone representation changes of one revision.

    ADK 2.11 stores an exact ISO datetime in this private attribute. Naive
    SQLite values represent UTC. A different instant or event history remains
    stale, even if the other check matches. The next append still performs ADK's
    concurrency check, so a writer racing after the read is rejected.
    """
    if fresh is None:
        return False
    markers = [getattr(item, "_storage_update_marker", None) for item in (session, fresh)]
    if not all(isinstance(marker, str) for marker in markers):
        return False
    try:
        revisions = [datetime.fromisoformat(marker) for marker in markers]
    except ValueError:
        return False
    revisions = [revision.replace(tzinfo=timezone.utc) if revision.tzinfo is None
                 else revision.astimezone(timezone.utc) for revision in revisions]
    if revisions[0] != revisions[1]:
        return False
    if [event.id for event in session.events] != [event.id for event in fresh.events]:
        return False
    session._storage_update_marker = fresh._storage_update_marker
    session.last_update_time = fresh.last_update_time
    return True


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
            f"Unsupported {ADK_DISTRIBUTION} version {installed}; expected {CERTIFIED_ADK_VERSION}."
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


def load_workflow_classes() -> tuple[Any, Any, Any, Any, Any]:
    """Load graph workflow primitives from ADK's public workflow API."""

    module = import_module("google.adk.workflow")
    return module.Workflow, module.FunctionNode, module.JoinNode, module.Edge, module.START


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
