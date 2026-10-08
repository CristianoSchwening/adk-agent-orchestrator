import asyncio
import json
from types import SimpleNamespace

import pytest

from orchestrator.config import MCPServerSettings, OrchestratorSettings
from orchestrator.mcp import describe_mcp_servers
from orchestrator.mcp.factory import connection_headers
from orchestrator.mcp.kev import decision_arguments, normalize_response, observe_task


def test_token_is_resolved_without_exposing_it(monkeypatch):
    server = MCPServerSettings.from_mapping({
        "name": "kev", "transport": "streamable_http",
        "url": "https://example.test/mcp", "bearer_token_env": "TEST_HF_TOKEN",
    })
    monkeypatch.setenv("TEST_HF_TOKEN", "private-token")
    assert connection_headers(server) == {"Authorization": "Bearer private-token"}
    assert "private-token" not in json.dumps(describe_mcp_servers(
        OrchestratorSettings(mcp_servers=(server,))
    ))
    monkeypatch.delenv("TEST_HF_TOKEN")
    assert connection_headers(server) == {}


def test_shadow_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("ADK_KEV_SHADOW_ENABLED", raising=False)
    assert not OrchestratorSettings.from_env().kev_shadow_enabled
    monkeypatch.setenv("ADK_KEV_SHADOW_ENABLED", "true")
    assert OrchestratorSettings.from_env().kev_shadow_enabled


def test_observation_minimizes_payload_and_survives_errors(monkeypatch):
    captured = []

    async def unavailable(settings, *, state):
        captured.append(json.loads(state))
        raise TimeoutError("sensitive upstream content")

    monkeypatch.setattr("orchestrator.mcp.kev.query_kev", unavailable)
    task = SimpleNamespace(
        title="Research", description="Find public docs", required_capabilities=["research"],
        user_profile={"secret": "not sent"}, dependency_results={"private": "not sent"},
    )
    result = asyncio.run(observe_task(OrchestratorSettings(), task))
    assert set(captured[0]) == {"title", "description", "required_capabilities"}
    assert result["status"] == "unavailable"
    assert result["error_type"] == "TimeoutError"
    assert "sensitive" not in json.dumps(result)


def test_decision_does_not_request_extra_gpu_work():
    args = decision_arguments("Synthetic task")
    assert args["calibrated"] is True
    assert args["check_stability"] is False
    assert args["model_choice"] == "Kev-4B"
    assert "n_perm" not in args  # Remote schema has conflicting string/integer constraints.
    assert "researcher_agent" in json.loads(args["questions_json"])["agent"]["criteria"]


def test_gradio_text_envelope_is_validated_without_html():
    names = json.loads(decision_arguments("test")["questions_json"])["agent"]["criteria"]
    response = {"model": "kev", "answers": {"agent": {
        "choice": "researcher_agent", "confidence": 0.5,
        "probabilities": {name: 0.2 for name in names},
    }}}
    payload = {"content": [{"type": "text", "text": repr(["<html/>", response, ""])}]}
    assert normalize_response(payload)["choice"] == "researcher_agent"
    assert "html" not in json.dumps(normalize_response(payload))
    response["answers"]["agent"]["probabilities"]["researcher_agent"] = -1
    payload["content"][0]["text"] = repr(["", response, ""])
    with pytest.raises(ValueError):
        normalize_response(payload)


def test_observations_survive_run_serialization_and_api_mapping():
    from orchestrator.dispatching.models import PlanRun, TaskRun
    from orchestrator.mapping import map_adk_execution

    observation = {"task_id": "t1", "status": "observed", "response": {
        "choice": "researcher_agent", "confidence": 0.7,
    }}
    run = PlanRun("run1", "plan1", "running", [
        TaskRun("t1", "ready", kev_observation=observation)
    ])
    assert PlanRun.from_dict(run.to_dict()).tasks[0].kev_observation == observation
    contract = map_adk_execution(
        session={"session_id": "s1", "state": {
            "kev_shadow_enabled": True, "kev_shadow_observations": [observation],
        }}, events=[], objective="Research", final_response="",
        settings=OrchestratorSettings(),
    )
    assert contract.metrics.custom["kev_shadow_enabled"] is True
    assert contract.metrics.custom["kev_shadow_observations"] == [observation]
    legacy = PlanRun.from_dict({"run_id": "r", "plan_id": "p", "status": "running",
                               "tasks": [{"task_id": "t", "status": "ready"}]})
    assert legacy.tasks[0].kev_observation is None
