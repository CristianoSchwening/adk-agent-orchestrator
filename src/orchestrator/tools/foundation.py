"""Foundation function tools used by the root ADK agent."""

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
    """Return the phase-5 capability status exposed to the ADK root agent."""

    return {
        "status": "ready",
        "phase": "phase_5_evaluation_production",
        "capabilities": [
            "root_agent",
            "runner",
            "in_memory_session_service",
            "in_memory_artifact_service",
            "sequential_workflow",
            "parallel_workflow",
            "review_critic_workflow",
            "iterative_refinement_workflow",
            "human_in_the_loop_workflow",
            "tool_catalog",
            "local_adk_function_tools",
            "mcp_toolset_factory",
            "tool_timeouts",
            "tool_error_standardization",
            "tool_usage_metrics",
            "execution_contract_v1",
            "adk_contract_mapper",
            "contract_snapshots",
            "continuous_evaluation",
            "evaluation_datasets",
            "structured_logging",
            "google_cloud_readiness",
            "production_runbooks",
        ],
    }
