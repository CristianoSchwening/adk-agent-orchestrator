"""Minimal function tools used by the root ADK agent in phase 1."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def capture_objective(objective: str) -> dict[str, Any]:
    """Capture a user objective as structured metadata for the session.

    The tool is intentionally side-effect free in phase 1. Future phases can
    persist the returned payload as an artifact or transform it into workflow
    state used by planner/dispatcher agents.
    """

    normalized_objective = objective.strip()
    return {
        "status": "success" if normalized_objective else "empty_objective",
        "objective": normalized_objective,
        "captured_at": datetime.now(UTC).isoformat(),
    }


def get_orchestrator_status() -> dict[str, Any]:
    """Return the phase-1 capability status exposed to the ADK root agent."""

    return {
        "status": "ready",
        "phase": "phase_1_foundation",
        "capabilities": [
            "root_agent",
            "runner",
            "in_memory_session_service",
            "in_memory_artifact_service",
        ],
    }
