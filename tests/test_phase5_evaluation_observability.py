from __future__ import annotations

import json
import logging
from pathlib import Path

from orchestrator.config import OrchestratorSettings
from orchestrator.evaluation import evaluate_dataset, load_dataset
from orchestrator.observability import ObservabilitySettings, emit_metric, get_logger
from orchestrator.runner import initial_session_state
from orchestrator.tools import get_orchestrator_status


def test_phase5_dataset_passes_deterministic_evaluation():
    result = evaluate_dataset("eval/datasets/phase5_smoke.json")

    assert result.passed
    assert result.total_cases == 3
    assert result.quality_score == 1.0
    assert result.safety_score == 1.0
    assert result.estimated_cost_usd == 0.0


def test_phase5_dataset_declares_thresholds_and_cases():
    dataset = load_dataset("eval/datasets/phase5_smoke.json")

    assert dataset["criteria"]["min_quality_score"] == 1.0
    assert {case["id"] for case in dataset["cases"]} == {
        "sequential-contract",
        "tools-mcp-readiness",
        "human-approval-safety",
    }


def test_status_and_initial_state_report_phase5():
    status = get_orchestrator_status()
    state = initial_session_state(OrchestratorSettings())

    assert status["phase"] == "phase_5_evaluation_production"
    assert "continuous_evaluation" in status["capabilities"]
    assert "google_cloud_readiness" in status["capabilities"]
    assert state["phase"] == "phase_5_evaluation_production"
    assert state["evaluation_dataset"] == "eval/datasets/phase5_smoke.json"


def test_observability_settings_and_metric_payload(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "orchestrator-service")
    monkeypatch.setenv("ADK_ENVIRONMENT", "staging")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")

    settings = ObservabilitySettings.from_env()
    payload = emit_metric(
        "evaluation_passed",
        1,
        labels={"dataset": "phase5_smoke"},
        settings=settings,
    )

    assert settings.service_name == "orchestrator-service"
    assert settings.environment == "staging"
    assert payload["metric_type"].endswith("/evaluation_passed")
    assert payload["labels"] == {"dataset": "phase5_smoke"}


def test_structured_logger_outputs_json(caplog):
    settings = ObservabilitySettings(service_name="svc", environment="test", log_level="INFO")
    logger = get_logger("test.phase5", settings)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    from orchestrator.observability.gcp import JsonFormatter

    handler.setFormatter(JsonFormatter(settings))
    logger.addHandler(handler)

    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        1,
        "hello",
        args=(),
        exc_info=None,
        extra={"json_fields": {"task_id": "task-1"}},
    )
    formatted = handler.format(record)
    parsed = json.loads(formatted)

    assert parsed["message"] == "hello"
    assert parsed["service"] == "svc"
    assert parsed["task_id"] == "task-1"


def test_runbook_docs_exist():
    for path in [
        Path("docs/runbooks/incident.md"),
        Path("docs/runbooks/rollback.md"),
        Path("docs/runbooks/agent_update.md"),
    ]:
        assert path.read_text(encoding="utf-8").startswith("# Runbook")
