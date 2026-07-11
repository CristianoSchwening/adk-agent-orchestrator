"""Rubric types for Loop 2 — Verification."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RubricCriterion:
    """A single evaluation criterion in a grading rubric."""

    name: str
    description: str
    threshold: float = 0.70
    weight: float = 1.0


@dataclass(frozen=True)
class CriterionResult:
    """Grader evaluation result for one criterion."""

    criterion: str
    score: float      # 0.0 – 1.0
    passed: bool
    feedback: str


@dataclass(frozen=True)
class GraderResult:
    """Complete rubric evaluation for one agent loop iteration."""

    passed: bool
    overall_score: float   # weighted average of criterion scores
    threshold: float
    iteration: int         # 0-indexed iteration number
    results: list[CriterionResult]
    overall_feedback: str


# ── Standard rubric used for generic quality evaluation ───────────────────────

STANDARD_QUALITY_RUBRIC: list[RubricCriterion] = [
    RubricCriterion(
        name="completeness",
        description="Does the output fully address all aspects of the objective?",
        threshold=0.70,
        weight=1.5,
    ),
    RubricCriterion(
        name="clarity",
        description="Is the content well-structured, coherent, and unambiguous?",
        threshold=0.65,
        weight=1.0,
    ),
    RubricCriterion(
        name="accuracy",
        description="Are all claims grounded, verifiable, and free of contradictions?",
        threshold=0.70,
        weight=1.5,
    ),
    RubricCriterion(
        name="actionability",
        description="Does the output provide concrete, executable next steps?",
        threshold=0.65,
        weight=1.0,
    ),
]
