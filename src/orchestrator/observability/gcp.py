"""Google Cloud friendly structured logging and metric helpers.

The helpers emit JSON to stdout/stderr by default so they work in Cloud Run,
GKE and local development without requiring Google Cloud client libraries.
Future production deployments can replace the sink with Cloud Logging/Monitoring
clients while preserving the payload schema.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ObservabilitySettings:
    """Settings used to enrich structured logs and metrics."""

    service_name: str = "adk-agent-orchestrator"
    environment: str = "local"
    google_cloud_project: str | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> ObservabilitySettings:
        return cls(
            service_name=os.getenv("K_SERVICE", cls.service_name).strip() or cls.service_name,
            environment=os.getenv("ADK_ENVIRONMENT", cls.environment).strip() or cls.environment,
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"),
            log_level=os.getenv("ADK_LOG_LEVEL", cls.log_level).strip() or cls.log_level,
        )


class JsonFormatter(logging.Formatter):
    """Format records as Cloud Logging compatible JSON."""

    def __init__(self, settings: ObservabilitySettings) -> None:
        super().__init__()
        self._settings = settings

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.now(UTC).isoformat(),
            "service": self._settings.service_name,
            "environment": self._settings.environment,
            "logger": record.name,
        }
        if self._settings.google_cloud_project:
            payload["logging.googleapis.com/projectId"] = self._settings.google_cloud_project
        if hasattr(record, "json_fields") and isinstance(record.json_fields, dict):
            payload.update(record.json_fields)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def get_logger(
    name: str = "orchestrator",
    settings: ObservabilitySettings | None = None,
) -> logging.Logger:
    """Return a logger configured for structured JSON output."""

    resolved = settings or ObservabilitySettings.from_env()
    logger = logging.getLogger(name)
    logger.setLevel(resolved.log_level.upper())
    if not any(getattr(handler, "_adk_json_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter(resolved))
        handler._adk_json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def emit_metric(
    name: str,
    value: int | float,
    *,
    labels: dict[str, str] | None = None,
    settings: ObservabilitySettings | None = None,
) -> dict[str, Any]:
    """Emit a metric-shaped structured log and return the payload."""

    resolved = settings or ObservabilitySettings.from_env()
    payload = {
        "metric_name": name,
        "metric_value": value,
        "metric_type": "custom.googleapis.com/adk_agent_orchestrator/" + name,
        "labels": labels or {},
        "resource": asdict(resolved),
    }
    get_logger("orchestrator.metrics", resolved).info(
        "metric emitted",
        extra={"json_fields": {"metric": payload}},
    )
    return payload
