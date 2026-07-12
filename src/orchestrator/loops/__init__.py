"""Loop engineering primitives — Loop 2: Verification, Loop 3: Event-Driven."""

from orchestrator.loops.rubric import (
    CriterionResult,
    GraderResult,
    RubricCriterion,
    STANDARD_QUALITY_RUBRIC,
)
from orchestrator.loops.verification import VerificationLoop
from orchestrator.loops.event_driven import EventLoop, ScheduleConfig, ExecutionSummary
from orchestrator.loops.stop_condition import (
    QualityStopCondition,
    StopReason,
    make_quality_stop_callback,
)

__all__ = [
    "CriterionResult",
    "GraderResult",
    "RubricCriterion",
    "STANDARD_QUALITY_RUBRIC",
    "VerificationLoop",
    "EventLoop",
    "ScheduleConfig",
    "ExecutionSummary",
    "QualityStopCondition",
    "StopReason",
    "make_quality_stop_callback",
]
