"""Loop 2 — Verification: rubric grader wrapping an agent workflow."""

from __future__ import annotations

import uuid
from typing import Literal

from orchestrator.contracts.dto import AgentVisibleResponse, utc_now_iso
from orchestrator.loops.rubric import CriterionResult, GraderResult, RubricCriterion

GraderType = Literal["feedback", "pass"]


class VerificationLoop:
    """
    Loop 2 — Verification.

    Wraps any agent workflow with a rubric-based grader. After each iteration
    the grader scores the output; if it fails the rubric the responses are
    marked *superseded* and the loop retries with corrective feedback, up to
    ``max_iterations`` attempts.

    In production the ``grade()`` method would delegate to an LLM-as-judge.
    In demo / test mode you can supply ``criterion_scores`` directly.
    """

    def __init__(
        self,
        rubric: list[RubricCriterion],
        max_iterations: int = 3,
        threshold: float | None = None,
    ) -> None:
        self.rubric = rubric
        self.max_iterations = max_iterations
        # Default overall threshold: weighted average of per-criterion thresholds
        total_w = sum(c.weight for c in rubric)
        self.threshold = threshold if threshold is not None else (
            sum(c.threshold * c.weight for c in rubric) / total_w
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def grade(
        self,
        responses: list[AgentVisibleResponse],
        iteration: int,
        criterion_scores: dict[str, float] | None = None,
    ) -> GraderResult:
        """
        Evaluate *responses* against the rubric and return a :class:`GraderResult`.

        *criterion_scores* is an optional override dict mapping criterion name →
        score (0-1). In production this would be replaced by an LLM-as-judge
        call that reads the response content and scores each criterion.
        """
        results: list[CriterionResult] = []
        for criterion in self.rubric:
            raw = (criterion_scores or {}).get(criterion.name, 0.5)
            score = max(0.0, min(1.0, float(raw)))
            passed = score >= criterion.threshold
            results.append(CriterionResult(
                criterion=criterion.name,
                score=score,
                passed=passed,
                feedback=_feedback_for(criterion.name, score, passed),
            ))

        total_w = sum(c.weight for c in self.rubric)
        overall = sum(r.score * c.weight for r, c in zip(results, self.rubric)) / total_w
        passed = overall >= self.threshold

        failed = [r for r in results if not r.passed]
        if passed:
            summary = (
                f"✅ All rubric criteria satisfied (score: {overall:.0%}). "
                "Output approved for publication."
            )
        else:
            names = ", ".join(r.criterion for r in failed)
            summary = (
                f"❌ Output failed rubric check (score: {overall:.0%} < "
                f"{self.threshold:.0%}). "
                f"Weak criteria: {names}. "
                "Please refine and retry."
            )

        return GraderResult(
            passed=passed,
            overall_score=round(overall, 4),
            threshold=self.threshold,
            iteration=iteration,
            results=results,
            overall_feedback=summary,
        )

    def grader_response(
        self,
        result: GraderResult,
        depends_on_ids: list[str],
        publication_order: int,
    ) -> AgentVisibleResponse:
        """Build an :class:`AgentVisibleResponse` representing the grader evaluation."""
        grader_type: GraderType = "pass" if result.passed else "feedback"

        lines = [result.overall_feedback, ""]
        for r in result.results:
            icon = "✅" if r.passed else "❌"
            lines.append(f"{icon} {r.criterion}: {r.score:.0%} — {r.feedback}")

        return AgentVisibleResponse(
            response_id=str(uuid.uuid4()),
            agent_name="rubric_grader",
            agent_role="Grader",
            content="\n".join(lines),
            depends_on_response_ids=depends_on_ids,
            visibility="internal",
            status="published",
            publication_order=publication_order,
            created_at=utc_now_iso(),
            metadata={
                "loop_iteration": result.iteration,
                "grader_type": grader_type,
                "overall_score": result.overall_score,
                "threshold": result.threshold,
                "passed": result.passed,
                "criterion_scores": {r.criterion: round(r.score, 4) for r in result.results},
            },
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

_FAILURE_MESSAGES: dict[str, str] = {
    "completeness":  "Too brief or missing key aspects",
    "clarity":       "Structure or wording is unclear",
    "accuracy":      "Contains unverified or contradictory claims",
    "actionability": "Lacks concrete, executable next steps",
}


def _feedback_for(criterion: str, score: float, passed: bool) -> str:
    if passed:
        return f"Meets threshold ({score:.0%})"
    base = _FAILURE_MESSAGES.get(criterion, "Below threshold")
    return f"{base} ({score:.0%})"
