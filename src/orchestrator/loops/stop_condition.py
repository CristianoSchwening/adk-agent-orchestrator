"""Stop condition callable for ADK LoopAgent.should_stop_loop.

Exposes:
  - StopReason      — Literal type for the two termination reasons
  - QualityStopCondition — Frozen dataclass callable that combines rubric
                           grading (VerificationLoop) with budget checking
                           (BudgetPolicy) to produce a per-tick stop decision.
  - make_quality_stop_callback — Convenience factory that returns a
                                  QualityStopCondition instance.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from typing import Any, Callable, Literal

from orchestrator.loops.verification import VerificationLoop
from orchestrator.policies.budget import BudgetPolicy

logger = logging.getLogger(__name__)

StopReason = Literal["quality_threshold_reached", "budget_exhausted"]


@dataclass(frozen=True)
class QualityStopCondition:
    """Callable stop predicate for ADK LoopAgent.should_stop_loop.

    Thread-safe: holds no mutable state; all counters are read from and
    written back to the ADK session_state dict on each invocation.

    Fields:
        verification_loop: VerificationLoop used to grade agent output.
        budget_policy:     BudgetPolicy that guards iteration/time budgets.
        output_key:        session_state key under which the agent writes output.
    """

    verification_loop: VerificationLoop
    budget_policy: BudgetPolicy
    output_key: str

    def __call__(self, session_state: dict[str, Any]) -> bool:
        """Return True when the loop should stop; False to continue.

        Side effects written to session_state on every call:
          grader_result         — dict representation of GraderResult
          loop_final_score      — float overall score from GraderResult
          loop_iterations_used  — int total iterations completed so far

        Written only when returning True:
          loop_stop_reason — "quality_threshold_reached" or "budget_exhausted"

        Always increments session_state["loop_iteration"] by 1.
        """
        # ── Req 1.10: guard against non-dict session state ────────────────
        if not isinstance(session_state, dict):
            logger.warning(
                "QualityStopCondition received non-dict session_state (got %s); "
                "returning False and deferring to max_iterations.",
                type(session_state).__name__,
            )
            return False

        # ── Read loop counters (default to 0 if absent) ───────────────────
        iteration: int = session_state.get("loop_iteration", 0)
        model_calls: int = session_state.get("loop_model_calls", 0)
        elapsed_ms: int = session_state.get("loop_elapsed_ms", 0)

        # ── Req 1.9: grade with exception safety ──────────────────────────
        try:
            result = self.verification_loop.grade_from_state(
                session_state, self.output_key, iteration
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "VerificationLoop.grade_from_state raised unexpectedly; "
                "treating as budget_exhausted and stopping loop."
            )
            session_state["loop_stop_reason"] = "budget_exhausted"
            return True

        # ── Evaluate stop conditions ──────────────────────────────────────
        quality_passed: bool = result.passed
        budget_ok: bool = self.budget_policy.should_continue(
            iterations=iteration,
            model_calls=model_calls,
            elapsed_ms=elapsed_ms,
        )

        stop: bool = quality_passed or (not budget_ok)

        # ── Req 1.7: always write diagnostics ────────────────────────────
        session_state["grader_result"] = dataclasses.asdict(result)
        session_state["loop_final_score"] = float(result.overall_score)
        session_state["loop_iterations_used"] = iteration + 1

        # ── Req 1.5/1.6: write stop reason only when stopping ────────────
        if stop:
            session_state["loop_stop_reason"] = (
                "quality_threshold_reached" if quality_passed else "budget_exhausted"
            )

        # ── Req 1.8: advance iteration counter ───────────────────────────
        session_state["loop_iteration"] = iteration + 1

        return stop


def make_quality_stop_callback(
    verification_loop: VerificationLoop,
    budget_policy: BudgetPolicy,
    output_key: str,
) -> Callable[[dict[str, Any]], bool]:
    """Return a QualityStopCondition ready to be passed to LoopAgent.should_stop_loop.

    Args:
        verification_loop: VerificationLoop instance that grades agent output.
        budget_policy:     BudgetPolicy that enforces iteration/time limits.
        output_key:        The session_state key the agent writes its output to.

    Returns:
        A QualityStopCondition callable — ``(session_state: dict) -> bool``.
    """
    return QualityStopCondition(
        verification_loop=verification_loop,
        budget_policy=budget_policy,
        output_key=output_key,
    )
