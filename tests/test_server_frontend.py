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
