"""Fresh-process API worker for durable human approval regression tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_human_interaction import configure_human_scenario

from orchestrator import server
from orchestrator.runner.human_runs import HumanRunStore


def main():
    root = Path(sys.argv[1])
    operation = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    counts_path = root / "calls.json"
    calls = (json.loads(counts_path.read_text(encoding="utf-8")) if counts_path.exists()
             else {"prepare": 0, "followup": 0, "first": 0})
    with pytest.MonkeyPatch.context() as patch:
        plan = configure_human_scenario(root, patch, operation["scenario"], calls)
        if operation["action"] == "interrupt_before_resume":
            async def interrupted(*args, **kwargs):
                raise RuntimeError("Simulated interruption after saving the decision")
            patch.setattr(server, "run_once_contract", interrupted)
        elif operation["action"] == "interrupt_after_resume":
            original_save = HumanRunStore.save

            def interrupted_save(self, run_id, value):
                if any(item.get("completed") for item in value["responses"].values()):
                    raise RuntimeError("Simulated interruption before saving the receipt")
                return original_save(self, run_id, value)

            patch.setattr(HumanRunStore, "save", interrupted_save)
        with TestClient(server.app, raise_server_exceptions=False) as client:
            if operation["action"] == "start":
                result = client.post("/api/run", json={"objective": plan.goal.objective})
            elif operation["action"] == "get":
                result = client.get(f"/api/runs/{operation['run_id']}")
            else:
                result = client.post(
                    f"/api/runs/{operation['run_id']}/human-requests/"
                    f"{operation['request_id']}/response", json=operation["answer"])
    counts_path.write_text(json.dumps(calls), encoding="utf-8")
    body = (result.json() if "application/json" in result.headers.get("content-type", "")
            else result.text)
    Path(sys.argv[3]).write_text(json.dumps({"status": result.status_code,
                                           "body": body, "calls": calls}),
                               encoding="utf-8")


if __name__ == "__main__":
    main()
