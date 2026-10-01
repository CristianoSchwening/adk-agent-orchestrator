"""Validated, criterion-level evidence for task acceptance decisions."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CriterionEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    criterion_id: str
    status: Literal["passed", "failed", "unverifiable"]
    rationale: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class TaskEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    trigger: Literal[
        "none", "blocker_detected", "assumption_invalidated",
        "objective_changed", "acceptance_criteria_failed",
    ]
    rationale: str = Field(min_length=1)
    criteria: list[CriterionEvaluation]


def criteria_catalog(criteria: list[str]) -> list[dict[str, str]]:
    """Keep IDs stable across reordering/revisions when criterion text is unchanged."""
    return [
        {"criterion_id": hashlib.sha256(text.encode()).hexdigest(), "text": text}
        for text in dict.fromkeys(criteria)
    ]


def validate_evaluation(value: dict, criteria: list[str]) -> dict:
    evaluation = TaskEvaluation.model_validate(value)
    catalog = criteria_catalog(criteria)
    expected = {item["criterion_id"] for item in catalog}
    actual = [item.criterion_id for item in evaluation.criteria]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("evaluation must cover every criterion exactly once")
    rejected = any(item.status != "passed" for item in evaluation.criteria)
    if evaluation.trigger == "none" and rejected:
        raise ValueError("approval contradicts criterion evaluations")
    if evaluation.trigger == "acceptance_criteria_failed" and not rejected:
        raise ValueError("acceptance failure requires a failed or unverifiable criterion")
    payload = evaluation.model_dump()
    payload["criteria_catalog"] = catalog
    return payload
