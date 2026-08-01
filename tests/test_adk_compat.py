from __future__ import annotations

from types import SimpleNamespace

import pytest

from orchestrator import adk_compat


def test_certified_adk_version_matches_dependency_pin():
    assert adk_compat.CERTIFIED_ADK_VERSION == "2.6.1"


def test_ensure_certified_adk_accepts_exact_version(monkeypatch):
    monkeypatch.setattr(adk_compat, "get_adk_version", lambda: "2.6.1")

    assert adk_compat.ensure_certified_adk() == "2.6.1"


@pytest.mark.parametrize("installed", [None, "2.5.0", "2.7.0"])
def test_ensure_certified_adk_rejects_missing_or_uncertified_version(monkeypatch, installed):
    monkeypatch.setattr(adk_compat, "get_adk_version", lambda: installed)

    with pytest.raises(RuntimeError, match="expected 2.6.1"):
        adk_compat.ensure_certified_adk()


def test_public_adk_loaders_use_supported_exports(monkeypatch):
    modules = {
        "google.adk": SimpleNamespace(Agent="agent", Runner="runner"),
        "google.adk.apps": SimpleNamespace(App="app"),
        "google.adk.agents": SimpleNamespace(
            SequentialAgent="sequential",
            ParallelAgent="parallel",
            LoopAgent="loop",
        ),
        "google.adk.sessions": SimpleNamespace(InMemorySessionService="session"),
        "google.adk.artifacts": SimpleNamespace(InMemoryArtifactService="artifact"),
        "google.genai.types": SimpleNamespace(Content="content", Part="part"),
        "google.adk.tools.mcp_tool": SimpleNamespace(
            McpToolset="mcp",
            StdioConnectionParams="stdio",
            SseConnectionParams="sse",
            StreamableHTTPConnectionParams="http",
        ),
        "mcp": SimpleNamespace(StdioServerParameters="stdio-server"),
    }
    monkeypatch.setattr(adk_compat, "import_module", modules.__getitem__)

    assert adk_compat.load_agent_class() == "agent"
    assert adk_compat.load_workflow_agent_classes() == ("sequential", "parallel", "loop")
    assert adk_compat.load_runtime_classes() == ("app", "runner", "session", "artifact")
    assert adk_compat.load_content_classes() == ("content", "part")
    assert adk_compat.load_mcp_classes() == (
        "mcp",
        "stdio-server",
        "stdio",
        "sse",
        "http",
    )
