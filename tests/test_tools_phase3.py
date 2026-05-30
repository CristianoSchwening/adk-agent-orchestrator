from __future__ import annotations

import json
import time

import pytest

from orchestrator.config import MCPServerSettings, OrchestratorSettings
from orchestrator.mcp import describe_mcp_servers
from orchestrator.tools import (
    describe_model_request,
    extract_document_outline,
    get_tool_usage_metrics,
    inspect_json_records,
    list_available_tools,
    read_text_file,
    reset_tool_usage_metrics,
)
from orchestrator.tools.runtime import execute_tool_call


def test_settings_include_tool_timeout_and_mcp_servers(monkeypatch):
    monkeypatch.setenv("ADK_TOOL_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv(
        "ADK_MCP_SERVERS",
        json.dumps(
            [
                {
                    "name": "filesystem",
                    "transport": "stdio",
                    "command": "mcp-filesystem",
                    "args": ["."],
                    "env": {"SAFE": "1"},
                }
            ]
        ),
    )

    settings = OrchestratorSettings.from_env()

    assert settings.tool_timeout_seconds == 2.5
    assert settings.mcp_servers == (
        MCPServerSettings(
            name="filesystem",
            transport="stdio",
            command="mcp-filesystem",
            args=(".",),
            env={"SAFE": "1"},
        ),
    )


@pytest.mark.parametrize("env_value", ["0", "-1", "not-a-number"])
def test_invalid_tool_timeout_is_rejected(monkeypatch, env_value):
    monkeypatch.setenv("ADK_TOOL_TIMEOUT_SECONDS", env_value)

    with pytest.raises(ValueError):
        OrchestratorSettings.from_env()


def test_list_available_tools_catalogs_phase3_categories():
    catalog = list_available_tools()

    assert catalog["status"] == "success"
    assert catalog["phase"] == "phase_3_tools_mcp"
    names = {tool["name"] for tool in catalog["tools"]}
    assert "read_text_file" in names
    assert "fetch_http_text" in names
    assert "create_configured_mcp_toolsets" in names


def test_local_tools_return_standard_payloads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "sample.md"
    sample_file.write_text("# Title\n\n## Details\nBody", encoding="utf-8")
    reset_tool_usage_metrics()

    file_result = read_text_file("sample.md")
    outline_result = extract_document_outline(file_result["data"]["text"])
    data_result = inspect_json_records('[{"name":"Ada","score":10},{"name":"Linus"}]')
    model_result = describe_model_request("summarize the result", model="gemini-test")

    assert file_result["status"] == "success"
    assert file_result["data"]["path"] == "sample.md"
    assert outline_result["data"]["heading_count"] == 2
    assert data_result["data"]["fields"] == {"name": ["str"], "score": ["int"]}
    assert model_result["data"]["will_call_model"] is False
    assert get_tool_usage_metrics()["total_calls"] == 4


def test_local_tool_errors_are_standardized(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reset_tool_usage_metrics()

    result = read_text_file("missing.txt")

    assert result["status"] == "error"
    assert result["error"]["code"] == "FileNotFoundError"
    metrics = get_tool_usage_metrics()
    assert metrics["by_tool"]["read_text_file"]["errors"] == 1


def test_execute_tool_call_timeout_records_metric():
    reset_tool_usage_metrics()

    result = execute_tool_call(
        "slow_tool",
        lambda: (time.sleep(0.05) or {"ok": True}),
        timeout_seconds=0.001,
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "timeout"
    metrics = get_tool_usage_metrics()
    assert metrics["by_tool"]["slow_tool"]["timeouts"] == 1


def test_describe_mcp_servers_does_not_create_connections():
    settings = OrchestratorSettings(
        mcp_servers=(
            MCPServerSettings(
                name="docs",
                transport="streamable_http",
                url="https://mcp.example.test/mcp",
            ),
        )
    )

    description = describe_mcp_servers(settings)

    assert description["status"] == "configured"
    assert description["servers"][0]["name"] == "docs"
    assert description["servers"][0]["transport"] == "streamable_http"
