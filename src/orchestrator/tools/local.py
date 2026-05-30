"""Local ADK function tools for filesystem, HTTP, documents, data and model planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from orchestrator.config import OrchestratorSettings
from orchestrator.tools.runtime import execute_tool_call


def _safe_workspace_path(path: str) -> Path:
    root = Path.cwd().resolve()
    candidate = (root / path).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("Path must stay within the current workspace.")
    if not candidate.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return candidate


def read_text_file(path: str, max_bytes: int = 32_768) -> dict[str, Any]:
    """Read a bounded UTF-8 text file from the current workspace."""

    def operation() -> dict[str, Any]:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero.")
        candidate = _safe_workspace_path(path)
        data = candidate.read_bytes()[:max_bytes]
        text = data.decode("utf-8", errors="replace")
        return {
            "path": str(candidate.relative_to(Path.cwd().resolve())),
            "bytes_read": len(data),
            "truncated": candidate.stat().st_size > max_bytes,
            "text": text,
        }

    return execute_tool_call("read_text_file", operation)


def fetch_http_text(
    url: str,
    max_bytes: int = 32_768,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Fetch bounded text content from an HTTP/HTTPS endpoint."""

    def operation() -> dict[str, Any]:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero.")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only http and https URLs are allowed.")

        timeout = timeout_seconds or OrchestratorSettings.from_env().tool_timeout_seconds
        request = Request(url, headers={"User-Agent": "adk-agent-orchestrator/phase3"})
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - scheme checked above
                body = response.read(max_bytes)
                content_type = response.headers.get("content-type", "")
                return {
                    "url": url,
                    "status_code": response.status,
                    "content_type": content_type,
                    "bytes_read": len(body),
                    "text": body.decode("utf-8", errors="replace"),
                }
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc

    return execute_tool_call("fetch_http_text", operation, timeout_seconds=timeout_seconds)


def extract_document_outline(text: str, max_headings: int = 20) -> dict[str, Any]:
    """Extract markdown-style headings and basic document statistics."""

    def operation() -> dict[str, Any]:
        if max_headings <= 0:
            raise ValueError("max_headings must be greater than zero.")
        lines = text.splitlines()
        headings: list[dict[str, Any]] = []
        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            marker_length = len(stripped) - len(stripped.lstrip("#"))
            if 1 <= marker_length <= 6 and stripped[marker_length:].startswith(" "):
                headings.append(
                    {
                        "line": line_number,
                        "level": marker_length,
                        "title": stripped[marker_length:].strip(),
                    }
                )
            if len(headings) >= max_headings:
                break
        return {
            "line_count": len(lines),
            "character_count": len(text),
            "heading_count": len(headings),
            "headings": headings,
        }

    return execute_tool_call("extract_document_outline", operation)


def inspect_json_records(json_text: str, sample_size: int = 5) -> dict[str, Any]:
    """Inspect JSON records and return a compact schema-like summary."""

    def operation() -> dict[str, Any]:
        if sample_size <= 0:
            raise ValueError("sample_size must be greater than zero.")
        payload = json.loads(json_text)
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = [payload]
        else:
            raise ValueError("JSON payload must be an object or array of objects.")

        sample = records[:sample_size]
        field_types: dict[str, set[str]] = {}
        for record in sample:
            if not isinstance(record, dict):
                continue
            for key, value in record.items():
                field_types.setdefault(str(key), set()).add(type(value).__name__)

        return {
            "record_count": len(records),
            "sample_size": len(sample),
            "fields": {
                key: sorted(type_names)
                for key, type_names in sorted(field_types.items(), key=lambda item: item[0])
            },
        }

    return execute_tool_call("inspect_json_records", operation)


def describe_model_request(task: str, model: str | None = None) -> dict[str, Any]:
    """Describe a safe model call plan without invoking a model."""

    def operation() -> dict[str, Any]:
        normalized_task = task.strip()
        if not normalized_task:
            raise ValueError("task must not be empty.")
        settings = OrchestratorSettings.from_env()
        selected_model = (model or settings.model).strip()
        return {
            "model": selected_model,
            "task": normalized_task,
            "will_call_model": False,
            "reason": "Phase 3 model tool cataloging does not invoke models directly.",
        }

    return execute_tool_call("describe_model_request", operation)
