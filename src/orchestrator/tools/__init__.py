"""Local ADK function tools for the orchestrator."""

from orchestrator.tools.catalog import list_available_tools
from orchestrator.tools.foundation import capture_objective, get_orchestrator_status
from orchestrator.tools.human import request_human_approval
from orchestrator.tools.local import (
    describe_model_request,
    extract_document_outline,
    fetch_http_text,
    inspect_json_records,
    read_text_file,
)
from orchestrator.tools.metrics import get_tool_usage_metrics, reset_tool_usage_metrics

PHASE_3_LOCAL_TOOLS = [
    list_available_tools,
    get_tool_usage_metrics,
    read_text_file,
    fetch_http_text,
    extract_document_outline,
    inspect_json_records,
    describe_model_request,
]

__all__ = [
    "PHASE_3_LOCAL_TOOLS",
    "capture_objective",
    "describe_model_request",
    "extract_document_outline",
    "fetch_http_text",
    "get_orchestrator_status",
    "get_tool_usage_metrics",
    "inspect_json_records",
    "list_available_tools",
    "read_text_file",
    "request_human_approval",
    "reset_tool_usage_metrics",
]
