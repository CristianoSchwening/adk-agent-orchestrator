"""Loop engineering primitives — Loop 2: Verification, Loop 3: Event-Driven."""

from orchestrator.loops.event_driven import EventLoop, ExecutionSummary, ScheduleConfig
from orchestrator.loops.rubric import (
    STANDARD_QUALITY_RUBRIC,
    CriterionResult,
    GraderResult,
    RubricCriterion,
)
from orchestrator.loops.stop_condition import (
    QualityStopCondition,
    StopReason,
    make_quality_stop_callback,
)
from orchestrator.loops.verification import VerificationLoop

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
