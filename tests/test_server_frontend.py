from fastapi.testclient import TestClient

from orchestrator.server import app, event_loop

client = TestClient(app)


def setup_function() -> None:
    event_loop.stop_schedule()
    event_loop.history.clear()


def test_loop3_config_exposes_webhook_and_empty_state() -> None:
    response = client.get("/api/loop3/config")

    assert response.status_code == 200
    data = response.json()
    assert data["webhook_token"]
    assert data["webhook_url"].endswith(data["webhook_token"])
    assert data["schedule"] is None
    assert data["history"] == []


def test_loop3_manual_trigger_records_demo_execution() -> None:
    response = client.post(
        "/api/loop3/trigger",
        json={"objective": "Validate the frontend", "workflow": "loop2_verification"},
    )

    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["source"] == "manual"
    assert run["response_count"] == 6
    assert run["verification_passed"] is True

    history = client.get("/api/loop3/config").json()["history"]
    assert history[0]["run_id"] == run["run_id"]


def test_loop3_webhook_rejects_invalid_token() -> None:
    response = client.post(
        "/api/loop3/webhook/invalid",
        json={"objective": "Rejected request", "workflow": "sequential"},
    )

    assert response.status_code == 404


def test_loop3_schedule_can_be_started_and_stopped() -> None:
    response = client.post(
        "/api/loop3/schedule",
        json={
            "objective": "Scheduled frontend check",
            "workflow": "sequential",
            "interval_seconds": 30,
            "active": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["active"] is True
    assert response.json()["next_run_at"] is not None

    stopped = client.delete("/api/loop3/schedule")
    assert stopped.status_code == 200
    assert stopped.json() == {"status": "stopped"}
    assert client.get("/api/loop3/config").json()["schedule"]["active"] is False


def test_loop3_schedule_rejects_short_interval() -> None:
    response = client.post(
        "/api/loop3/schedule",
        json={
            "objective": "Too frequent",
            "workflow": "sequential",
            "interval_seconds": 1,
            "active": True,
        },
    )

    assert response.status_code == 422


def test_run_routes_requested_workflow_to_runtime(monkeypatch) -> None:
    from types import SimpleNamespace

    from orchestrator import server

    captured: dict[str, str | None] = {}

    async def fake_run_once_contract(objective, *, settings, workflow):
        captured["objective"] = objective
        captured["workflow"] = workflow
        return SimpleNamespace(
            decision_metadata=SimpleNamespace(selected_workflow=workflow),
            to_dict=lambda: {
                "decision_metadata": {"selected_workflow": workflow},
                "progressive_agent_responses": [],
            },
        )

    monkeypatch.setattr(server, "run_once_contract", fake_run_once_contract)
    response = client.post(
        "/api/run",
        json={"objective": "Qual a capital de Brasilia?", "workflow": "parallel"},
    )

    assert response.status_code == 200
    assert captured == {
        "objective": "Qual a capital de Brasilia?",
        "workflow": "parallel",
    }


def test_run_preserves_canonical_progressive_response_payload(monkeypatch) -> None:
    from types import SimpleNamespace

    from orchestrator import server

    canonical = {
        "response_id": "response-x",
        "agent_name": "progressive_agent_a",
        "agent_role": "dynamic_specialist",
        "content": "Conteúdo estruturado original",
        "depends_on_response_ids": [],
        "visibility": "user_visible",
        "status": "published",
        "publication_order": 1,
        "created_at": "2026-08-17T00:00:00+00:00",
        "metadata": {"source": "runtime", "nested": {"preserved": True}},
    }

    async def fake_run_once_contract(objective, *, settings, workflow):
        return SimpleNamespace(
            to_dict=lambda: {
                "decision_metadata": {"selected_workflow": workflow},
                "progressive_agent_responses": [canonical],
            }
        )

    monkeypatch.setattr(server, "run_once_contract", fake_run_once_contract)

    response = client.post(
        "/api/run",
        json={"objective": "Teste estruturado", "workflow": "progressive_multi_agent_response"},
    )

    assert response.status_code == 200
    assert response.json()["progressive_agent_responses"] == [canonical]


def test_run_maps_legacy_verification_name_to_iterative_workflow(monkeypatch) -> None:
    from orchestrator import server

    captured: dict[str, str | None] = {}

    async def fake_run_once_contract(objective, *, settings, workflow):
        captured["workflow"] = workflow
        raise RuntimeError("stop after routing")

    monkeypatch.setattr(server, "run_once_contract", fake_run_once_contract)
    response = client.post(
        "/api/run",
        json={"objective": "Teste", "workflow": "loop2_verification"},
    )

    assert response.status_code == 500
    assert captured["workflow"] == "iterative_refinement"


def test_run_rejects_unknown_workflow_before_runtime() -> None:
    response = client.post(
        "/api/run",
        json={"objective": "Teste", "workflow": "unknown"},
    )

    assert response.status_code == 422
    assert "supported_workflows" in response.json()["detail"]
