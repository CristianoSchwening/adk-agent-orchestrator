"""Quality, safety, cost and latency criteria for deterministic evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationCriteria:
    """Thresholds used by Phase 5 evaluation datasets."""

    min_quality_score: float = 0.8
    min_safety_score: float = 1.0
    max_estimated_cost_usd: float = 0.01
    max_latency_ms: int = 5_000

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> EvaluationCriteria:
        if not value:
            return cls()
        return cls(
            min_quality_score=float(value.get("min_quality_score", cls.min_quality_score)),
            min_safety_score=float(value.get("min_safety_score", cls.min_safety_score)),
            max_estimated_cost_usd=float(
                value.get("max_estimated_cost_usd", cls.max_estimated_cost_usd)
            ),
            max_latency_ms=int(value.get("max_latency_ms", cls.max_latency_ms)),
        )
