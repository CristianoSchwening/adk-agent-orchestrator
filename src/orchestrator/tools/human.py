"""Human-in-the-loop function tools for ADK workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

ApprovalDecision = Literal["approved", "rejected", "needs_changes"]


def request_human_approval(
    decision: ApprovalDecision,
    rationale: str,
    requested_action: str,
) -> dict[str, Any]:
    """Capture a human approval decision as structured ADK tool output."""

    return {
        "status": "recorded",
        "decision": decision,
        "rationale": rationale.strip(),
        "requested_action": requested_action.strip(),
        "approved": decision == "approved",
        "recorded_at": datetime.now(UTC).isoformat(),
    }
