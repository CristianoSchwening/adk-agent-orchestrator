"""FastAPI webapp server exposing the ExecutionContractDTO as a REST API."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.config import OrchestratorSettings
from orchestrator.contracts.dto import (
    CONTRACT_VERSION,
    AgentVisibleResponse,
    utc_now_iso,
)
from orchestrator.runner.bootstrap import build_runtime, initial_session_state, run_once_contract

WEBAPP_DIR = Path(__file__).parent.parent.parent / "webapp"
REACT_BUILD_DIR = WEBAPP_DIR / "static"

app = FastAPI(title="ADK Orchestrator UI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    objective: str
    workflow: str | None = None


class StatusResponse(BaseModel):
    status: str
    contract_version: str
    adk_installed: bool


@app.get("/api/status")
async def get_status() -> StatusResponse:
    from orchestrator.adk_compat import is_adk_installed

    return StatusResponse(
        status="ready",
        contract_version=CONTRACT_VERSION,
        adk_installed=is_adk_installed(),
    )


@app.post("/api/run")
async def run_objective(body: RunRequest) -> JSONResponse:
    objective = body.objective.strip()
    if not objective:
        raise HTTPException(status_code=422, detail="objective must not be empty")

    settings = OrchestratorSettings.from_env()

    try:
        contract = await run_once_contract(objective, settings=settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    data = contract.to_dict()

    if body.workflow == "progressive_multi_agent_response":
        data["progressive_agent_responses"] = _build_progressive_responses(contract)

    return JSONResponse(content=data)


@app.post("/api/run/demo")
async def run_demo(body: RunRequest) -> JSONResponse:
    """Return a richly-populated demo contract without calling a real model."""

    objective = body.objective.strip() or "Demo objective"
    now = utc_now_iso()
    workflow = body.workflow or "sequential"

    session_id = f"demo-{uuid.uuid4()}"
    task_id = str(uuid.uuid4())

    data: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "task": {
            "task_id": task_id,
            "objective": objective,
            "status": "completed",
            "app_name": "adk-agent-orchestrator",
            "user_id": "demo-user",
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "final_response": (
                f"Objective '{objective}' completed successfully via the {workflow} "
                "workflow. All sub-agents finished their assigned tasks and the "
                "result has been consolidated."
            ),
        },
        "subtasks": [
            {
                "subtask_id": "sequential:plan",
                "name": "plan",
                "status": "completed",
                "agent_name": "sequential_planner_agent",
                "workflow": workflow,
                "input_summary": objective,
                "output_summary": "Broke the objective into 3 actionable steps.",
                "started_at": now,
                "finished_at": now,
                "error": None,
            },
            {
                "subtask_id": "sequential:execute",
                "name": "execute",
                "status": "completed",
                "agent_name": "sequential_executor_agent",
                "workflow": workflow,
                "input_summary": "Execute 3 steps from plan.",
                "output_summary": "All steps executed. Output validated.",
                "started_at": now,
                "finished_at": now,
                "error": None,
            },
            {
                "subtask_id": "sequential:critique",
                "name": "critique",
                "status": "completed",
                "agent_name": "sequential_critic_agent",
                "workflow": workflow,
                "input_summary": "Review execution output.",
                "output_summary": (
                    "Output meets quality criteria. No revisions needed."
                ),
                "started_at": now,
                "finished_at": now,
                "error": None,
            },
            {
                "subtask_id": "sequential:summarize",
                "name": "summarize",
                "status": "completed",
                "agent_name": "sequential_summarizer_agent",
                "workflow": workflow,
                "input_summary": "Consolidate results.",
                "output_summary": "Summary produced and attached to final response.",
                "started_at": now,
                "finished_at": now,
                "error": None,
            },
        ],
        "events": [
            {
                "event_id": "event-1",
                "type": "model",
                "message": f"Root agent received objective: {objective}",
                "timestamp": now,
                "source": "root_orchestrator_agent",
                "severity": "info",
                "subtask_id": None,
                "metadata": {},
            },
            {
                "event_id": "event-2",
                "type": "tool_call",
                "message": "capture_objective called",
                "timestamp": now,
                "source": "root_orchestrator_agent",
                "severity": "info",
                "subtask_id": None,
                "metadata": {"tool": "capture_objective"},
            },
            {
                "event_id": "event-3",
                "type": "tool_response",
                "message": "capture_objective → success",
                "timestamp": now,
                "source": "root_orchestrator_agent",
                "severity": "info",
                "subtask_id": None,
                "metadata": {"tool": "capture_objective"},
            },
            {
                "event_id": "event-4",
                "type": "model",
                "message": "Planner produced a 3-step execution plan.",
                "timestamp": now,
                "source": "sequential_planner_agent",
                "severity": "info",
                "subtask_id": "sequential:plan",
                "metadata": {},
            },
            {
                "event_id": "event-5",
                "type": "model",
                "message": "Executor completed all steps successfully.",
                "timestamp": now,
                "source": "sequential_executor_agent",
                "severity": "info",
                "subtask_id": "sequential:execute",
                "metadata": {},
            },
            {
                "event_id": "event-6",
                "type": "model",
                "message": "Critic approved output without revisions.",
                "timestamp": now,
                "source": "sequential_critic_agent",
                "severity": "info",
                "subtask_id": "sequential:critique",
                "metadata": {},
            },
            {
                "event_id": "event-7",
                "type": "final_response",
                "message": "Summarizer produced final consolidated response.",
                "timestamp": now,
                "source": "sequential_summarizer_agent",
                "severity": "info",
                "subtask_id": "sequential:summarize",
                "metadata": {},
            },
        ],
        "metrics": {
            "duration_ms": 3241,
            "event_count": 7,
            "subtask_count": 4,
            "artifact_count": 4,
            "tool_call_count": 2,
            "model_event_count": 4,
            "error_count": 0,
            "custom": {
                "phase": "phase_5_evaluation_production",
                "tool_timeout_seconds": 10.0,
                "mcp_server_count": 0,
            },
        },
        "decision_metadata": {
            "selected_workflow": workflow,
            "rationale": (
                f"The objective '{objective}' maps best to the {workflow} "
                "workflow based on its multi-step nature."
            ),
            "confidence": 0.91,
            "alternatives": [
                w for w in ["sequential", "parallel", "review_critic"]
                if w != workflow
            ],
            "policy_version": "v1.0",
        },
        "artifacts": [
            {
                "artifact_id": "demo-architecture-preview",
                "name": "architecture-preview.svg",
                "mime_type": "image/svg+xml",
                "uri": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 360'%3E%3Crect width='640' height='360' fill='%231a1d27'/%3E%3Ccircle cx='160' cy='180' r='70' fill='%236366f1'/%3E%3Ccircle cx='320' cy='180' r='70' fill='%2306b6d4'/%3E%3Ccircle cx='480' cy='180' r='70' fill='%2322c55e'/%3E%3Ctext x='320' y='310' text-anchor='middle' fill='%23e2e8f0' font-family='Inter, sans-serif' font-size='28'%3EADK artifact preview%3C/text%3E%3C/svg%3E",
                "size_bytes": 18432,
                "metadata": {"version": "1"},
            },
            {
                "artifact_id": "demo-execution-report",
                "name": "execution-report.pdf",
                "mime_type": "application/pdf",
                "uri": "artifact://demo/execution-report.pdf",
                "size_bytes": 245760,
                "metadata": {"version": "1"},
            },
            {
                "artifact_id": "demo-agent-trace",
                "name": "agent-trace.json",
                "mime_type": "application/json",
                "uri": "artifact://demo/agent-trace.json",
                "size_bytes": 9216,
                "metadata": {"version": "1"},
            },
            {
                "artifact_id": "demo-voice-summary",
                "name": "voice-summary.mp3",
                "mime_type": "audio/mpeg",
                "uri": "artifact://demo/voice-summary.mp3",
                "size_bytes": 524288,
                "metadata": {"version": "1"},
            },
        ],
        "progressive_agent_responses": [],
    }

    if workflow == "progressive_multi_agent_response":
        r1 = str(uuid.uuid4())
        r2 = str(uuid.uuid4())
        r3 = str(uuid.uuid4())
        r4 = str(uuid.uuid4())
        r5 = str(uuid.uuid4())
        data["progressive_agent_responses"] = [
            {
                "response_id": r1,
                "agent_name": "planner_agent",
                "agent_role": "Planner",
                "content": (
                    f"Analyzed objective: '{objective}'.\n\nExecution plan:\n1. "
                    "Research the problem domain\n2. Synthesize findings in "
                    "parallel\n3. Draft and validate the final output"
                ),
                "depends_on_response_ids": [],
                "visibility": "user_visible",
                "status": "published",
                "publication_order": 1,
                "created_at": now,
                "metadata": {"confidence": 0.95, "steps_planned": 3},
            },
            {
                "response_id": r2,
                "agent_name": "researcher_agent",
                "agent_role": "Researcher",
                "content": (
                    "Research complete. Key findings:\n- Domain is "
                    "well-documented with established patterns\n- 3 highly "
                    "relevant prior approaches identified\n- No blocking "
                    "dependencies found"
                ),
                "depends_on_response_ids": [r1],
                "visibility": "user_visible",
                "status": "published",
                "publication_order": 2,
                "created_at": now,
                "metadata": {"sources": 3, "coverage": "high"},
            },
            {
                "response_id": r3,
                "agent_name": "executor_agent",
                "agent_role": "Executor",
                "content": (
                    "Internal validation log:\n- Pattern A applied ✓\n- "
                    "Pattern B applied ✓\n- Pattern C applied ✓\n"
                    "All checks passed."
                ),
                "depends_on_response_ids": [r1],
                "visibility": "internal",
                "status": "published",
                "publication_order": 3,
                "created_at": now,
                "metadata": {"patterns_applied": 3, "validation": "passed"},
            },
            {
                "response_id": r4,
                "agent_name": "critic_agent",
                "agent_role": "Critic",
                "content": (
                    "⚠ Initial draft flagged for revision — confidence below "
                    "threshold. Requesting refinement."
                ),
                "depends_on_response_ids": [r2, r3],
                "visibility": "user_visible",
                "status": "superseded",
                "publication_order": 4,
                "created_at": now,
                "metadata": {"revision_reason": "confidence_below_threshold"},
            },
            {
                "response_id": r5,
                "agent_name": "summarizer_agent",
                "agent_role": "Summarizer",
                "content": (
                    f"✅ Final consolidated response for '{objective}':\n\n"
                    "All agent contributions have been reviewed and integrated. "
                    "The objective has been fulfilled with high confidence. "
                    "The approach is grounded in 3 validated patterns and "
                    "passed all quality checks."
                ),
                "depends_on_response_ids": [r2, r3, r4],
                "visibility": "user_visible",
                "status": "published",
                "publication_order": 5,
                "created_at": now,
                "metadata": {"final": True, "confidence": 0.97},
            },
        ]

    return JSONResponse(content=data)


def _build_progressive_responses(contract: Any) -> list[dict[str, Any]]:
    """Map contract subtasks → AgentVisibleResponse-shaped dicts."""

    ROLE_MAP = {
        "plan": "Planner",
        "execute": "Executor",
        "critique": "Critic",
        "summarize": "Summarizer",
        "research": "Researcher",
        "refine": "Refiner",
        "approval": "Approver",
    }

    responses = []
    prev_id: str | None = None
    for order, subtask in enumerate(contract.subtasks, start=1):
        rid = str(uuid.uuid4())
        role = ROLE_MAP.get(subtask.name, subtask.name.capitalize())
        responses.append(
            {
                "response_id": rid,
                "agent_name": subtask.agent_name or subtask.name,
                "agent_role": role,
                "content": subtask.output_summary or subtask.name,
                "depends_on_response_ids": [prev_id] if prev_id else [],
                "visibility": "user_visible",
                "status": (
                    "published"
                    if subtask.status == "completed"
                    else subtask.status
                ),
                "publication_order": order,
                "created_at": subtask.finished_at or utc_now_iso(),
                "metadata": {
                    "subtask_id": subtask.subtask_id,
                    "workflow": subtask.workflow,
                },
            }
        )
        prev_id = rid
    return responses


if REACT_BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(REACT_BUILD_DIR)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    index = REACT_BUILD_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Frontend not built")
    return FileResponse(str(index))


@app.get("/{path:path}")
async def serve_spa(path: str) -> FileResponse:
    target = REACT_BUILD_DIR / path
    if target.exists() and target.is_file():
        return FileResponse(str(target))
    index = REACT_BUILD_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404, detail="Not found")
