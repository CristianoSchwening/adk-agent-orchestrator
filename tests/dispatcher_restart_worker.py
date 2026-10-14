"""Exercise a dispatcher action interrupted by an actual process exit."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from google.adk.workflow import FunctionNode
from test_human_interaction import configure_human_scenario

from orchestrator import server
from orchestrator.agents import task_dispatcher
from orchestrator.config import OrchestratorSettings
from orchestrator.runner import bootstrap


def main():
    root = Path(sys.argv[1])
    action, failure = sys.argv[2:4]
    with pytest.MonkeyPatch.context() as patch:
        plan = configure_human_scenario(root, patch, "approved",
                                        {"first": 0, "prepare": 0, "followup": 0})

        def executor(settings, **kwargs):
            def effect(ctx, node_input):
                (root / "identity.json").write_text(json.dumps({
                    "session_id": ctx.session.id, "invocation_id": ctx.invocation_id}),
                    encoding="utf-8")
                if failure == "after":
                    with (root / "effects.txt").open("a", encoding="utf-8") as stream:
                        stream.write("external action\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                os._exit(23)
            return FunctionNode(func=effect, name=kwargs["name"])

        patch.setattr(task_dispatcher, "create_executor_agent", executor)
        if action == "start":
            with TestClient(server.app) as client:
                client.post("/api/run", json={"objective": plan.goal.objective})
        else:
            identity = json.loads((root / "identity.json").read_text(encoding="utf-8"))
            settings = OrchestratorSettings(workspace_enabled=False, task_run_root="runs",
                                            task_plan_root="plans")
            runtime = bootstrap.build_runtime(
                settings, session_db=str(root / "executions" / "sessions.sqlite"))

            async def resume():
                try:
                    async for _ in runtime.runner.run_async(
                            user_id=settings.user_id, new_message=None, **identity):
                        pass
                finally:
                    await runtime.session_service.close()

            asyncio.run(resume())


if __name__ == "__main__":
    main()
