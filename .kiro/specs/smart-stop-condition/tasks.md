# Implementation Plan: Smart Stop Condition

## Overview

Wire `VerificationLoop.grade()` and `BudgetPolicy.should_continue()` into a new
`QualityStopCondition` callable that is passed as `should_stop_loop` to ADK `LoopAgent`.
Both `review_critic_workflow` and `iterative_refinement_workflow` will stop early when
the output satisfies the quality rubric threshold or any budget dimension is exhausted.
All changes are additive; `VerificationLoop` remains usable standalone without ADK.

## Tasks

- [x] 1. Add `quality_threshold` field to `BudgetPolicy`
  - [x] 1.1 Add `quality_threshold: float = 0.70` field to the `BudgetPolicy` frozen dataclass in `src/orchestrator/policies/budget.py`
    - Keep `frozen=True`; add the field after `max_elapsed_ms`
    - No other logic changes needed in this file
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 1.2 Write property test for `BudgetPolicy.quality_threshold` default and custom values
    - **Property 6: Quality threshold consistency** — for all `threshold ∈ [0.0, 1.0]`, `BudgetPolicy(quality_threshold=threshold).quality_threshold == threshold`
    - **Validates: Requirements 4.1, 4.3**
    - Use `hypothesis` `@given(floats(min_value=0.0, max_value=1.0))` strategy
    - Place tests in `tests/test_smart_stop_condition.py`

- [x] 2. Add `grade_from_state` method to `VerificationLoop`
  - [x] 2.1 Implement `grade_from_state(self, session_state, output_key, iteration, criterion_scores=None)` on `VerificationLoop` in `src/orchestrator/loops/verification.py`
    - Dispatch on the type of `session_state.get(output_key)`:
      - `str` → wrap in a synthetic `AgentVisibleResponse` and call `grade()`
      - `list` of `AgentVisibleResponse` → pass directly to `grade()`
      - `None` / absent / other → call `grade([], iteration)` (all scores 0.0)
    - Must not import any ADK symbol
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 2.2 Write property test for `grade_from_state` equivalence with `grade`
    - **Property 7: Standalone usability** — `grade_from_state` produces the same `GraderResult` as calling `grade()` directly with equivalent inputs
    - **Validates: Requirements 3.6, 8.5**
    - Test with string input, list input, and `None` input across hypothesis-generated `criterion_scores`

  - [ ]* 2.3 Write unit tests for `grade_from_state` edge cases
    - Test: absent key → `passed=False`, all scores `0.0`
    - Test: `None` value → `passed=False`
    - Test: non-string / non-list value → `passed=False`, no exception raised
    - _Requirements: 3.3, 3.4, 3.5_

- [x] 3. Checkpoint — ensure `BudgetPolicy` and `VerificationLoop` changes pass all tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Create `loops/stop_condition.py` with `StopReason`, `QualityStopCondition`, and `make_quality_stop_callback`
  - [x] 4.1 Create `src/orchestrator/loops/stop_condition.py` with the `StopReason` literal type and the `QualityStopCondition` frozen dataclass skeleton
    - Define `StopReason = Literal["quality_threshold_reached", "budget_exhausted"]`
    - Define `@dataclass(frozen=True) class QualityStopCondition` with fields `verification_loop`, `budget_policy`, `output_key`
    - _Requirements: 7.1, 7.3, 1.1_

  - [x] 4.2 Implement `QualityStopCondition.__call__(self, session_state)` in `src/orchestrator/loops/stop_condition.py`
    - Guard: if `session_state` is not a `dict`, log `WARNING` and return `False` (Requirement 1.10)
    - Read `loop_iteration` (default 0), `loop_model_calls` (default 0), `loop_elapsed_ms` (default 0) from state
    - Wrap `verification_loop.grade_from_state(...)` in `try/except Exception`; on exception write `"budget_exhausted"` and return `True` (Requirement 1.9)
    - Evaluate `quality_passed = result.passed` and `budget_ok = budget_policy.should_continue(...)`
    - Compute `stop = quality_passed or (not budget_ok)`
    - Write `grader_result` (via `dataclasses.asdict`), `loop_final_score`, `loop_iterations_used` on every call (Requirement 1.7)
    - Write `loop_stop_reason` only when `stop=True`; never write it when continuing (Requirements 1.5, 1.6)
    - Increment `session_state["loop_iteration"]` by exactly 1 (Requirement 1.8)
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

  - [x] 4.3 Implement `make_quality_stop_callback` factory in `src/orchestrator/loops/stop_condition.py`
    - Accept `verification_loop`, `budget_policy`, `output_key` and return `QualityStopCondition(...)`
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 4.4 Write property test for stop reason completeness (Property 3)
    - **Property 3: Stop reason completeness** — whenever `__call__` returns `True`, `session_state["loop_stop_reason"]` is `"quality_threshold_reached"` or `"budget_exhausted"`; when it returns `False`, the key is absent or `None`
    - **Validates: Requirements 1.5, 1.6**
    - Generate arbitrary `criterion_scores` via `hypothesis`; parametrize over quality pass / budget fail combinations

  - [ ]* 4.5 Write property test for monotonic iteration counter (Property 4)
    - **Property 4: Monotonic iteration counter** — `loop_iterations_used` always equals `old(loop_iteration) + 1` after each call; `loop_iteration` increments by exactly 1
    - **Validates: Requirements 1.7, 1.8**
    - Drive with hypothesis-generated initial `loop_iteration` values

  - [ ]* 4.6 Write property test for score range invariant (Property 2)
    - **Property 2: Score range invariant** — for any `criterion_scores ∈ [0.0, 1.0]^n` with positive weights, `loop_final_score ∈ [0.0, 1.0]`
    - **Validates: Requirements 8.2**
    - Use `hypothesis` `floats(min_value=0.0, max_value=1.0)` for scores

  - [ ]* 4.7 Write property test for budget consistency (Property 5)
    - **Property 5: Budget consistency** — if `BudgetPolicy.should_continue(...)` returns `False` for the current iteration values, `QualityStopCondition.__call__` must return `True`
    - **Validates: Requirements 1.4, 8.6**
    - Construct states where budget is exhausted and assert `stop=True`

  - [ ]* 4.8 Write unit tests for `QualityStopCondition.__call__` control paths
    - Test: quality pass → `stop=True`, `loop_stop_reason="quality_threshold_reached"`
    - Test: budget exhausted → `stop=True`, `loop_stop_reason="budget_exhausted"`
    - Test: both continue → `stop=False`, `loop_stop_reason` absent
    - Test: `grade_from_state` raises → `stop=True`, `loop_stop_reason="budget_exhausted"`, no propagation
    - Test: `session_state` not a dict → `stop=False`, no exception
    - _Requirements: 1.5, 1.6, 1.9, 1.10_

- [x] 5. Export new symbols from `loops/__init__.py`
  - [x] 5.1 Add `QualityStopCondition`, `make_quality_stop_callback`, and `StopReason` to the imports and `__all__` list in `src/orchestrator/loops/__init__.py`
    - Import from `orchestrator.loops.stop_condition`
    - _Requirements: 7.2_

- [x] 6. Checkpoint — ensure stop condition module and exports pass all tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Update `mapping/adk.py` — add `grader_result` to `WORKFLOW_STATE_KEYS` and loop diagnostics to `MetricsDTO.custom`
  - [x] 7.1 Add `"grader_result": ("loop", "grade")` to the `WORKFLOW_STATE_KEYS` dict in `src/orchestrator/mapping/adk.py`
    - _Requirements: 6.5_

  - [x] 7.2 Extend the `custom` dict in `MetricsDTO(...)` inside `map_adk_execution` to include `loop_stop_reason`, `loop_final_score`, and `loop_iterations_used`
    - Read each from `state.get(key)` so missing keys yield `None`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 7.3 Write unit tests for `map_adk_execution` loop diagnostics
    - Test: state with all three keys populated → values appear in `contract.metrics.custom`
    - Test: state missing all three keys → all values are `None` in `contract.metrics.custom`
    - Test: `grader_result` key present in state → `SubtaskDTO` for `("loop", "grade")` is included in `contract.subtasks`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 8. Wire `QualityStopCondition` into workflow factories in `agents/workflows.py`
  - [ ] 8.1 Add `_build_loop_agent_kwargs(base_kwargs, stop_callback)` internal helper in `src/orchestrator/agents/workflows.py`
    - Use `inspect.signature(LoopAgent.__init__)` to probe for `should_stop_loop`
    - If found, add `"should_stop_loop": stop_callback` to `base_kwargs`
    - If not found, log `WARNING` and return `base_kwargs` unchanged
    - Catch `ImportError` and `AttributeError` silently and return `base_kwargs` unchanged
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ] 8.2 Update `create_review_critic_workflow` in `src/orchestrator/agents/workflows.py` to construct a `VerificationLoop` and `QualityStopCondition`, then pass the callback via `_build_loop_agent_kwargs`
    - Build `VerificationLoop(rubric=STANDARD_QUALITY_RUBRIC, max_iterations=policy.max_iterations, threshold=policy.quality_threshold)`
    - Call `make_quality_stop_callback(v_loop, policy, output_key="review_candidate")`
    - Replace the direct `LoopAgent(...)` call with `LoopAgent(**_build_loop_agent_kwargs({...}, stop_callback))`
    - _Requirements: 4.4, 5.4_

  - [ ] 8.3 Update `create_iterative_refinement_workflow` in `src/orchestrator/agents/workflows.py` in the same pattern as 8.2 with `output_key="refinement_result"`
    - _Requirements: 4.4, 5.5_

  - [ ]* 8.4 Write property test for graceful degradation (Property 8)
    - **Property 8: Graceful degradation** — when a mock `LoopAgent` does not accept `should_stop_loop`, `_build_loop_agent_kwargs` returns `base_kwargs` unchanged and logs at WARNING level; no exception is raised
    - **Validates: Requirements 5.3, 5.6**
    - Parametrize with mock `LoopAgent` classes that have and don't have `should_stop_loop`

  - [ ]* 8.5 Write property test for termination guarantee (Property 1)
    - **Property 1: Termination guarantee** — for any finite `max_iterations`, the accumulated `loop_iterations_used` across successive `QualityStopCondition.__call__` invocations never exceeds `max_iterations + 1`
    - **Validates: Requirements 8.1**
    - Simulate a loop driving `QualityStopCondition` until it returns `True`; assert total calls ≤ `max_iterations + 1`

  - [ ]* 8.6 Write property test for quality threshold consistency (Property 6)
    - **Property 6: Quality threshold consistency** — if `GraderResult.passed=True` then `overall_score >= threshold`; if `GraderResult.passed=False` then `overall_score < threshold`
    - **Validates: Requirements 8.3, 8.4**
    - Drive `VerificationLoop.grade()` with hypothesis-generated `criterion_scores` and arbitrary `threshold` values

- [ ] 9. Final checkpoint — ensure all tests pass end to end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- `hypothesis` must be added to `[project.optional-dependencies].dev` in `pyproject.toml` before running property tests (current dev deps include `pytest` and `ruff` but not `hypothesis`)
- Each task references specific requirements for traceability
- Checkpoints at tasks 3, 6, and 9 ensure incremental validation
- Property tests validate universal correctness properties; unit tests validate specific examples and edge cases
- All property tests live in `tests/test_smart_stop_condition.py`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3"] },
    { "id": 4, "tasks": ["4.4", "4.5", "4.6", "4.7", "4.8", "5.1"] },
    { "id": 5, "tasks": ["7.1", "7.2"] },
    { "id": 6, "tasks": ["7.3", "8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3"] },
    { "id": 8, "tasks": ["8.4", "8.5", "8.6"] }
  ]
}
```
