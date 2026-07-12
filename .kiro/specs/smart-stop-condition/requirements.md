# Requirements Document

## Introduction

This feature wires `VerificationLoop.grade()` and `BudgetPolicy.should_continue()` into a
new `QualityStopCondition` callable that is passed as the `should_stop_loop` callback to
ADK `LoopAgent`. The `review_critic_workflow` and `iterative_refinement_workflow` currently
exhaust all `max_iterations` before stopping. After this feature, those workflows stop early
whenever the output satisfies the quality rubric threshold or any budget dimension is
exhausted — whichever comes first.

`VerificationLoop` remains usable as a standalone component without ADK. The integration is
additive and degrades gracefully when the installed ADK version does not expose the
`should_stop_loop` parameter.

---

## Glossary

- **QualityStopCondition**: Frozen dataclass callable that reads agent output from ADK session
  state, grades it via `VerificationLoop`, checks budget via `BudgetPolicy`, writes diagnostic
  state keys, and returns `bool` to signal the `LoopAgent` to stop.
- **make_quality_stop_callback**: Factory function that constructs and returns a
  `QualityStopCondition` instance compatible with `LoopAgent.should_stop_loop`.
- **VerificationLoop**: Existing class in `loops/verification.py` that evaluates agent output
  against a rubric and produces a `GraderResult`. No ADK dependency.
- **grade_from_state**: New method on `VerificationLoop` that extracts agent output from ADK
  session state and delegates to the existing `grade()` method.
- **BudgetPolicy**: Existing frozen dataclass in `policies/budget.py` that guards iteration,
  model-call, and elapsed-time budgets. Extended with a `quality_threshold` field.
- **GraderResult**: Existing frozen dataclass in `loops/rubric.py` representing the complete
  rubric evaluation result for one loop iteration.
- **StopReason**: Literal type with values `"quality_threshold_reached"` and
  `"budget_exhausted"` written to session state when the loop terminates early.
- **session_state**: The mutable `dict[str, Any]` managed by ADK and passed to the
  `should_stop_loop` callback on every `LoopAgent` tick.
- **output_key**: The session state key under which the loop's primary agent writes its output
  (e.g., `"review_candidate"`, `"refinement_result"`).
- **STANDARD_QUALITY_RUBRIC**: Existing list of four `RubricCriterion` objects
  (completeness, clarity, accuracy, actionability) used as the default rubric.
- **_build_loop_agent_kwargs**: Internal helper in `agents/workflows.py` that probes the ADK
  `LoopAgent` signature and conditionally injects `should_stop_loop`.
- **MetricsDTO**: Existing DTO in `contracts/dto.py` whose `custom` field is extended with
  `loop_stop_reason`, `loop_final_score`, and `loop_iterations_used`.
- **load_symbol**: Utility in `orchestrator.adk_compat` for lazy, fault-tolerant import of
  ADK symbols — used to probe `LoopAgent` signature without hard-wiring the ADK version.

---

## Requirements

### Requirement 1: QualityStopCondition Callable

**User Story:** As a workflow developer, I want a single callable that combines rubric grading
and budget checking so that I can wire it as a `LoopAgent.should_stop_loop` callback without
writing ad-hoc stop logic in each workflow factory.

#### Acceptance Criteria

1. THE `QualityStopCondition` SHALL be a frozen dataclass with exactly three fields:
   `verification_loop: VerificationLoop`, `budget_policy: BudgetPolicy`, and
   `output_key: str`.
2. WHEN `QualityStopCondition.__call__` is invoked with a `session_state` dict, THE
   `QualityStopCondition` SHALL read `session_state[output_key]` to obtain the current agent
   output for grading.
3. WHEN `QualityStopCondition.__call__` is invoked, THE `QualityStopCondition` SHALL delegate
   scoring to `VerificationLoop.grade_from_state(session_state, output_key, iteration)`.
4. WHEN `QualityStopCondition.__call__` is invoked, THE `QualityStopCondition` SHALL delegate
   budget checking to `BudgetPolicy.should_continue(iterations, model_calls, elapsed_ms)`.
5. WHEN `QualityStopCondition.__call__` returns `True`, THE `QualityStopCondition` SHALL write
   `session_state["loop_stop_reason"]` to either `"quality_threshold_reached"` (when
   `GraderResult.passed` is `True`) or `"budget_exhausted"` (when `BudgetPolicy.should_continue`
   returns `False`).
6. WHEN `QualityStopCondition.__call__` returns `False`, THE `QualityStopCondition` SHALL leave
   `session_state["loop_stop_reason"]` absent or `None`; it SHALL NOT write `loop_stop_reason`
   when the loop continues.
7. WHEN `QualityStopCondition.__call__` is invoked, THE `QualityStopCondition` SHALL write
   `grader_result` (dict representation of `GraderResult` via `dataclasses.asdict`),
   `loop_final_score` (float overall score), and `loop_iterations_used` (int total iterations
   completed so far) to `session_state` on every invocation regardless of whether the call
   returns `True` or `False`.
8. WHEN `QualityStopCondition.__call__` is invoked, THE `QualityStopCondition` SHALL increment
   `session_state["loop_iteration"]` by exactly 1, initialising it to 0 if absent.
9. IF `VerificationLoop.grade_from_state` raises an unexpected exception, THEN THE
   `QualityStopCondition` SHALL return `True` and write
   `session_state["loop_stop_reason"] = "budget_exhausted"` without propagating the exception.
10. IF `session_state` is not a `dict`, THEN THE `QualityStopCondition` SHALL return `False`
    and log a `WARNING`-level message without raising.

---

### Requirement 2: make_quality_stop_callback Factory

**User Story:** As a workflow developer, I want a convenience factory so that I can obtain a
`QualityStopCondition` callable with a single call and pass it directly to `LoopAgent`.

#### Acceptance Criteria

1. THE `make_quality_stop_callback` function SHALL accept `verification_loop: VerificationLoop`,
   `budget_policy: BudgetPolicy`, and `output_key: str` as parameters.
2. THE `make_quality_stop_callback` function SHALL return a `QualityStopCondition` instance
   constructed from the provided arguments.
3. THE `make_quality_stop_callback` function SHALL be importable from `loops/stop_condition.py`
   alongside `QualityStopCondition`.

---

### Requirement 3: VerificationLoop grade_from_state Method

**User Story:** As a developer testing workflows, I want `VerificationLoop` to be callable
directly against ADK session state so that I can grade output without extracting it manually,
while keeping `VerificationLoop` free of any ADK import.

#### Acceptance Criteria

1. THE `VerificationLoop` SHALL expose a `grade_from_state(self, session_state, output_key,
   iteration, criterion_scores=None)` method that returns a `GraderResult`.
2. WHEN `session_state[output_key]` is a `str`, THE `grade_from_state` method SHALL wrap it in a
   synthetic `AgentVisibleResponse` and pass it to `grade()`.
3. WHEN `session_state[output_key]` is a `list` of `AgentVisibleResponse` objects, THE
   `grade_from_state` method SHALL pass the list directly to `grade()`.
4. WHEN `session_state[output_key]` is absent or `None`, THE `grade_from_state` method SHALL
   call `grade([], iteration)` so that all criteria score `0.0` and `GraderResult.passed`
   is `False`.
5. WHEN `session_state[output_key]` contains a value that is neither `str` nor
   `list[AgentVisibleResponse]`, THE `grade_from_state` method SHALL fall back to
   `grade([], iteration)` and SHALL NOT raise.
6. THE `grade_from_state` method SHALL NOT import or reference any ADK symbol, preserving the
   standalone usability of `VerificationLoop`.

---

### Requirement 4: BudgetPolicy Quality Threshold Field

**User Story:** As a workflow developer, I want the quality threshold to live in `BudgetPolicy`
alongside the iteration and time limits so that all stop-condition parameters are configured
from a single policy object.

#### Acceptance Criteria

1. THE `BudgetPolicy` dataclass SHALL include a `quality_threshold: float` field with default
   value `0.70`.
2. THE `BudgetPolicy` SHALL remain a frozen dataclass (`frozen=True`) after adding the new
   field, consistent with the pattern in `contracts/dto.py`.
3. WHEN `BudgetPolicy` is instantiated without specifying `quality_threshold`, THE
   `BudgetPolicy` SHALL default to `quality_threshold = 0.70`.
4. WHEN `create_review_critic_workflow` or `create_iterative_refinement_workflow` constructs a
   `VerificationLoop`, THE workflow factory SHALL pass `policy.quality_threshold` as the
   `threshold` argument to `VerificationLoop`.

---

### Requirement 5: Workflow Wiring via _build_loop_agent_kwargs

**User Story:** As a system operator, I want both loop workflows to stop early when quality
is reached, while still working correctly on older ADK versions that do not expose the
`should_stop_loop` parameter.

#### Acceptance Criteria

1. THE `agents/workflows.py` module SHALL define a `_build_loop_agent_kwargs(base_kwargs,
   stop_callback)` internal helper that returns a `dict` to be unpacked into `LoopAgent(...)`.
2. WHEN `LoopAgent.__init__` accepts a `should_stop_loop` parameter (as detected via
   `inspect.signature`), THE `_build_loop_agent_kwargs` helper SHALL add
   `"should_stop_loop": stop_callback` to the returned dict.
3. WHEN `LoopAgent.__init__` does not accept `should_stop_loop`, THE `_build_loop_agent_kwargs`
   helper SHALL omit that key from the returned dict and log a `WARNING`-level message stating
   that the workflow is falling back to `max_iterations`-only termination.
4. WHEN `create_review_critic_workflow` is called, THE workflow factory SHALL construct a
   `QualityStopCondition` with `output_key="review_candidate"` and pass it to
   `_build_loop_agent_kwargs`.
5. WHEN `create_iterative_refinement_workflow` is called, THE workflow factory SHALL construct
   a `QualityStopCondition` with `output_key="refinement_result"` and pass it to
   `_build_loop_agent_kwargs`.
6. IF `inspect.signature` or `LoopAgent.__init__` raises `ImportError` or `AttributeError`,
   THEN THE `_build_loop_agent_kwargs` helper SHALL silently ignore the error and return
   `base_kwargs` unchanged.

---

### Requirement 6: Loop Diagnostics in MetricsDTO.custom

**User Story:** As a UI developer, I want to read loop stop reason, final quality score, and
iteration count directly from the execution contract so that I can display workflow efficiency
metrics without additional API calls.

#### Acceptance Criteria

1. THE `map_adk_execution` function SHALL include `loop_stop_reason`, `loop_final_score`, and
   `loop_iterations_used` in `MetricsDTO.custom`, reading each from the corresponding
   session state key.
2. WHEN `session_state["loop_stop_reason"]` is `None` or absent, THE `MetricsDTO.custom`
   SHALL include `"loop_stop_reason": None`.
3. WHEN `session_state["loop_final_score"]` is `None` or absent, THE `MetricsDTO.custom`
   SHALL include `"loop_final_score": None`.
4. WHEN `session_state["loop_iterations_used"]` is `None` or absent, THE `MetricsDTO.custom`
   SHALL include `"loop_iterations_used": None`.
5. THE `WORKFLOW_STATE_KEYS` dict in `mapping/adk.py` SHALL include the entry
   `"grader_result": ("loop", "grade")` so that grader output is surfaced as a subtask in
   the execution contract.

---

### Requirement 7: loops/stop_condition.py Module and Exports

**User Story:** As a developer, I want `QualityStopCondition` and `make_quality_stop_callback`
available from the `loops` package so that they can be imported with the same ergonomics as
existing loop utilities.

#### Acceptance Criteria

1. THE `loops/stop_condition.py` module SHALL be created as the sole location for
   `QualityStopCondition`, `make_quality_stop_callback`, and `StopReason`.
2. THE `loops/__init__.py` SHALL export `QualityStopCondition` and `make_quality_stop_callback`
   alongside existing loop exports.
3. THE `StopReason` type SHALL be defined as
   `Literal["quality_threshold_reached", "budget_exhausted"]` in `loops/stop_condition.py`.

---

### Requirement 8: Correctness and Safety Guarantees

**User Story:** As an SRE, I want the stop condition to be provably safe so that it never
causes a workflow to hang, never corrupts session state, and degrades gracefully under any
input.

#### Acceptance Criteria

1. FOR ALL finite `max_iterations` values in `BudgetPolicy`, THE `LoopAgent` SHALL always
   terminate — either via `GraderResult.passed`, `BudgetPolicy.should_continue` returning
   `False`, or `LoopAgent` exhausting `max_iterations` — guaranteeing the callback never
   prevents termination.
2. FOR ALL `criterion_scores` values in `[0.0, 1.0]` and positive weights,
   THE `VerificationLoop.grade` SHALL return `overall_score` in `[0.0, 1.0]`.
3. WHEN `GraderResult.passed` is `True`, THE `GraderResult.overall_score` SHALL be greater
   than or equal to `verification_loop.threshold`.
4. WHEN `GraderResult.passed` is `False`, THE `GraderResult.overall_score` SHALL be strictly
   less than `verification_loop.threshold`.
5. THE `VerificationLoop.grade` and `VerificationLoop.grade_from_state` SHALL produce
   equivalent `GraderResult` values when given logically equivalent inputs, regardless of
   whether ADK is installed.
6. WHEN `BudgetPolicy.should_continue` returns `False`, THE `QualityStopCondition.__call__`
   SHALL return `True` for the same session state values.
