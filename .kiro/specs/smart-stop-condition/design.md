# Design Document: Smart Stop Condition

## Overview

`LoopAgent` workflows (`review_critic_workflow` and `iterative_refinement_workflow`) currently
exhaust all iterations before stopping. This feature wires `VerificationLoop.grade()` and
`BudgetPolicy.should_continue()` into a new `QualityStopCondition` that is passed as the
`should_stop_loop` callback to `LoopAgent`, enabling early exit when the output satisfies
the quality rubric or when any budget dimension is exhausted.

`VerificationLoop` remains fully usable as a standalone component without ADK. The integration
is additive and degrades gracefully when the installed ADK version does not expose the
`should_stop_loop` parameter.

---

## Architecture

### High-Level Component Map

```
┌────────────────────────────────────────────────────────────────────────┐
│  agents/workflows.py                                                   │
│                                                                        │
│  create_review_critic_workflow()          create_iterative_refinement  │
│  ┌──────────────────────────────┐         _workflow()                  │
│  │ LoopAgent                    │         ┌──────────────────────────┐ │
│  │  max_iterations = policy.N   │         │ LoopAgent                │ │
│  │  should_stop_loop = ──────── ┼──┐      │  max_iterations = policy │ │
│  │  sub_agents=[author, critic] │  │      │  should_stop_loop = ──── ┼─┼──┐
│  └──────────────────────────────┘  │      │  sub_agents=[drafter,    │ │  │
└────────────────────────────────────┼──────┤   evaluator, refiner]    │ │  │
                                     │      └──────────────────────────┘ │  │
                                     │  ┌─────────────────────────────────┘  │
                                     │  │                                     │
                                     ▼  ▼                                     │
┌────────────────────────────────────────────────────────────────────────┐    │
│  loops/stop_condition.py                                               │    │
│                                                                        │    │
│  make_quality_stop_callback(verification_loop, budget_policy,          │◄───┘
│                              output_key)  → Callable[[dict], bool]    │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────┐         │
│  │ QualityStopCondition                                      │         │
│  │  .verification_loop : VerificationLoop  ────────────────►│─────────┼──► loops/verification.py
│  │  .budget_policy     : BudgetPolicy  ────────────────────►│─────────┼──► policies/budget.py
│  │  .output_key        : str                                │         │
│  │  .__call__(session_state) → bool                         │         │
│  └──────────────────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────────┐     ┌──────────────────────────┐
│ loops/verification  │     │ policies/budget.py        │
│                     │     │                           │
│ VerificationLoop    │     │ BudgetPolicy              │
│  .grade()           │     │  .quality_threshold=0.70  │
│  .grade_from_state()│     │  .should_continue()       │
└─────────────────────┘     └──────────────────────────┘
         │
         │ writes GraderResult to state["grader_result"]
         ▼
┌─────────────────────────────────┐
│ ADK Session State (dict)        │
│  output_key → agent output text │
│  grader_result → GraderResult   │
│  loop_stop_reason → str         │
│  loop_iteration → int           │
└─────────────────────────────────┘
         │
         │ read by
         ▼
┌─────────────────────────────────┐
│ mapping/adk.py                  │
│  MetricsDTO.custom              │
│    loop_stop_reason             │
│    loop_final_score             │
│    loop_iterations_used         │
└─────────────────────────────────┘
```


### Data Flow: Per-Iteration Stop Decision

```
ADK LoopAgent tick N
        │
        │  calls should_stop_loop(session_state)
        ▼
QualityStopCondition.__call__(state)
        │
        ├─ 1. read state[output_key]  ──────► extract responses list
        │
        ├─ 2. VerificationLoop.grade_from_state(state, output_key, iteration)
        │         │
        │         └─► grade(responses, iteration)  →  GraderResult
        │                   │
        │                   └─► state["grader_result"] = GraderResult
        │
        ├─ 3. BudgetPolicy.should_continue(iterations, model_calls, elapsed_ms)
        │         │
        │         └─► budget_ok : bool
        │
        ├─ 4. stop = GraderResult.passed OR (NOT budget_ok)
        │
        ├─ 5. state["loop_stop_reason"] =
        │         "quality_threshold_reached" if passed
        │         "budget_exhausted"          if NOT budget_ok
        │         None                        (loop continues)
        │
        └─► return stop : bool
```

---

## Components and Interfaces

### Component 1: `QualityStopCondition` (`loops/stop_condition.py`)

**Purpose:** Callable value object that reads agent output from ADK session state,
grades it via `VerificationLoop`, checks budget via `BudgetPolicy`, writes diagnostic
state keys, and returns `True` to signal the `LoopAgent` to stop.

**Interface:**

```python
@dataclass(frozen=True)
class QualityStopCondition:
    verification_loop: VerificationLoop
    budget_policy: BudgetPolicy
    output_key: str

    def __call__(self, session_state: dict[str, Any]) -> bool: ...
```

**Responsibilities:**
- Read `session_state[output_key]` to obtain the current agent output.
- Derive `responses: list[AgentVisibleResponse]` from the raw state value.
- Increment and track the iteration counter stored in `session_state["loop_iteration"]`.
- Delegate scoring to `VerificationLoop.grade_from_state()`.
- Delegate budget check to `BudgetPolicy.should_continue()`.
- Write `grader_result`, `loop_stop_reason`, `loop_final_score`, `loop_iterations_used`
  back to session state.
- Be safe to call from an async context (no blocking I/O, no mutable shared state).

---

### Component 2: `make_quality_stop_callback` factory (`loops/stop_condition.py`)

**Purpose:** Convenience factory that wires `VerificationLoop` + `BudgetPolicy` into a
plain callable compatible with `LoopAgent.should_stop_loop`, with graceful degradation
when the ADK version does not support that parameter.

**Interface:**

```python
def make_quality_stop_callback(
    verification_loop: VerificationLoop,
    budget_policy: BudgetPolicy,
    output_key: str,
) -> Callable[[dict[str, Any]], bool]: ...
```

---

### Component 3: `VerificationLoop.grade_from_state` (`loops/verification.py`)

**Purpose:** Thin helper that extracts responses from session state and delegates to
`grade()`, keeping `VerificationLoop` usable standalone without ADK.

**Interface:**

```python
def grade_from_state(
    self,
    session_state: dict[str, Any],
    output_key: str,
    iteration: int,
    criterion_scores: dict[str, float] | None = None,
) -> GraderResult: ...
```

---

### Component 4: `BudgetPolicy` update (`policies/budget.py`)

**Purpose:** Add `quality_threshold` field so budget and quality threshold live in
a single policy object, eliminating the need to pass the threshold separately to
`VerificationLoop`.

**Interface:**

```python
@dataclass(frozen=True)
class BudgetPolicy:
    max_iterations: int = 3
    max_model_calls: int = 12
    max_elapsed_ms: int = 120_000
    quality_threshold: float = 0.70

    def should_continue(
        self, *, iterations: int, model_calls: int, elapsed_ms: int
    ) -> bool: ...
```

---

### Component 5: `WORKFLOW_STATE_KEYS` + `MetricsDTO.custom` (`mapping/adk.py`)

**Purpose:** Surface loop stop diagnostics in the execution contract.

**New state keys mapped:**

```python
WORKFLOW_STATE_KEYS update:
    "grader_result": ("loop", "grade"),
```

**`MetricsDTO.custom` additions (in `map_adk_execution`):**

```python
custom={
    ...,
    "loop_stop_reason":     state.get("loop_stop_reason"),       # str | None
    "loop_final_score":     state.get("loop_final_score"),       # float | None
    "loop_iterations_used": state.get("loop_iterations_used"),   # int | None
}
```


---

## Data Models

### `StopReason` (literal type, `loops/stop_condition.py`)

```python
StopReason = Literal[
    "quality_threshold_reached",
    "budget_exhausted",
]
```

**Stored in** `session_state["loop_stop_reason"]` when the loop terminates early.
Left absent (or `None`) when the loop continues or exhausts `max_iterations` naturally.

---

### `GraderResult` (existing, `loops/rubric.py`)

Frozen dataclass — no changes to fields.

Written to `session_state["grader_result"]` as a plain `dict` via `dataclasses.asdict()`
so it survives ADK session serialization without importing `loops` from the mapping layer.

---

## Low-Level Design

### Full Signatures

#### `loops/stop_condition.py`

```python
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Literal

from orchestrator.loops.rubric import GraderResult
from orchestrator.loops.verification import VerificationLoop
from orchestrator.policies.budget import BudgetPolicy

StopReason = Literal["quality_threshold_reached", "budget_exhausted"]


@dataclass(frozen=True)
class QualityStopCondition:
    """Callable stop predicate for ADK LoopAgent.should_stop_loop.

    Thread-safe: holds no mutable state; all counters are read from and
    written back to the ADK session_state dict on each invocation.
    """

    verification_loop: VerificationLoop
    budget_policy: BudgetPolicy
    output_key: str

    def __call__(self, session_state: dict[str, Any]) -> bool:
        """Return True when the loop should stop; False to continue.

        Side effects (written to session_state):
          grader_result       – dict representation of GraderResult
          loop_stop_reason    – StopReason string when stopping, absent otherwise
          loop_final_score    – float overall score from last GraderResult
          loop_iterations_used – int total iterations completed so far
        """
        ...


def make_quality_stop_callback(
    verification_loop: VerificationLoop,
    budget_policy: BudgetPolicy,
    output_key: str,
) -> Callable[[dict[str, Any]], bool]:
    """Return a QualityStopCondition callable, or a no-op if not needed.

    Intended to be passed directly as LoopAgent(should_stop_loop=...).
    Returns QualityStopCondition(verification_loop, budget_policy, output_key).
    """
    ...
```

#### `loops/verification.py` — new method on `VerificationLoop`

```python
def grade_from_state(
    self,
    session_state: dict[str, Any],
    output_key: str,
    iteration: int,
    criterion_scores: dict[str, float] | None = None,
) -> GraderResult:
    """Extract responses from session_state[output_key] and grade them.

    Falls back gracefully if the key is absent or the value is not a
    recognised response format — scores all criteria at 0.0 so the loop
    can still make a deterministic stop decision.
    """
    ...
```

#### `policies/budget.py` — updated dataclass

```python
@dataclass(frozen=True)
class BudgetPolicy:
    max_iterations: int = 3
    max_model_calls: int = 12
    max_elapsed_ms: int = 120_000
    quality_threshold: float = 0.70  # NEW — mirrors VerificationLoop default

    def should_continue(
        self, *, iterations: int, model_calls: int, elapsed_ms: int
    ) -> bool:
        """Return True iff all three budget dimensions are within limits."""
        ...
```


---

### Algorithmic Pseudocode

#### `QualityStopCondition.__call__`

```pascal
PROCEDURE QualityStopCondition.__call__(session_state)
  INPUT:  session_state : dict  { ADK mutable session state }
  OUTPUT: stop : bool

  PRECONDITIONS:
    session_state IS a dict (may be empty)
    self.verification_loop IS a VerificationLoop instance
    self.budget_policy IS a BudgetPolicy instance
    self.output_key IS a non-empty str

  BEGIN
    // ── 1. Read iteration counter ────────────────────────────────────────
    iteration ← session_state.get("loop_iteration", 0)

    // ── 2. Read model_calls and elapsed_ms from state (0 if absent) ──────
    model_calls ← session_state.get("loop_model_calls", 0)
    elapsed_ms  ← session_state.get("loop_elapsed_ms",  0)

    // ── 3. Grade current output ──────────────────────────────────────────
    result ← self.verification_loop.grade_from_state(
        session_state, self.output_key, iteration
    )

    // ── 4. Evaluate stop conditions ──────────────────────────────────────
    quality_passed ← result.passed
    budget_ok      ← self.budget_policy.should_continue(
        iterations=iteration,
        model_calls=model_calls,
        elapsed_ms=elapsed_ms
    )

    stop ← quality_passed OR (NOT budget_ok)

    // ── 5. Write diagnostics back to state ───────────────────────────────
    session_state["grader_result"]        ← asdict(result)
    session_state["loop_final_score"]     ← result.overall_score
    session_state["loop_iterations_used"] ← iteration + 1

    IF quality_passed THEN
      session_state["loop_stop_reason"] ← "quality_threshold_reached"
    ELSE IF NOT budget_ok THEN
      session_state["loop_stop_reason"] ← "budget_exhausted"
    END IF

    // ── 6. Advance iteration counter ─────────────────────────────────────
    session_state["loop_iteration"] ← iteration + 1

    RETURN stop
  END

  POSTCONDITIONS:
    IF stop = true THEN session_state["loop_stop_reason"] IS set
    session_state["grader_result"] IS a dict representation of GraderResult
    session_state["loop_iterations_used"] = old(iteration) + 1
    stop = true IFF result.passed = true OR budget_ok = false

  LOOP INVARIANT (across LoopAgent ticks):
    session_state["loop_iteration"] increases by exactly 1 per call
    session_state["grader_result"]  always reflects the most recent grade
END
```

#### `VerificationLoop.grade_from_state`

```pascal
PROCEDURE VerificationLoop.grade_from_state(session_state, output_key, iteration,
                                             criterion_scores=None)
  INPUT:  session_state   : dict
          output_key      : str
          iteration       : int  (0-indexed)
          criterion_scores: dict[str, float] | None
  OUTPUT: result : GraderResult

  PRECONDITIONS:
    output_key IS a non-empty str
    iteration >= 0

  BEGIN
    raw ← session_state.get(output_key)

    IF raw IS None THEN
      // Graceful degradation: no output yet, score everything 0
      responses ← []
    ELSE IF raw IS list[AgentVisibleResponse] THEN
      responses ← raw
    ELSE IF raw IS str THEN
      responses ← [synthetic AgentVisibleResponse(content=raw)]
    ELSE
      responses ← []
    END IF

    RETURN self.grade(responses, iteration, criterion_scores)
  END

  POSTCONDITIONS:
    Always returns a valid GraderResult (never raises)
    When raw IS None: result.passed = false (all scores = 0.0)
END
```

#### Graceful Degradation: `should_stop_loop` Parameter Absence

```pascal
PROCEDURE make_quality_stop_callback(verification_loop, budget_policy, output_key)
  INPUT:  verification_loop, budget_policy, output_key
  OUTPUT: callback : Callable[[dict], bool]

  BEGIN
    condition ← QualityStopCondition(verification_loop, budget_policy, output_key)
    RETURN condition
  END
```

```pascal
PROCEDURE _build_loop_agent_kwargs(base_kwargs, stop_callback)
  // Called inside create_review_critic_workflow and
  // create_iterative_refinement_workflow when constructing LoopAgent
  INPUT:  base_kwargs   : dict   { name, description, max_iterations, sub_agents }
          stop_callback : Callable

  BEGIN
    TRY
      // Probe whether ADK LoopAgent accepts should_stop_loop
      import inspect
      sig ← inspect.signature(LoopAgent.__init__)

      IF "should_stop_loop" IN sig.parameters THEN
        base_kwargs["should_stop_loop"] ← stop_callback
      ELSE
        // Older ADK: log warning, continue without quality gate
        LOG warning("LoopAgent does not support should_stop_loop; "
                    "falling back to max_iterations only")
      END IF

    EXCEPT ImportError OR AttributeError
      // ADK not available (test environment): ignore
    END TRY

    RETURN base_kwargs
  END
```


---

### `agents/workflows.py` — Updated Workflow Factories

```pascal
PROCEDURE create_review_critic_workflow(settings, budget_policy)
  BEGIN
    policy ← budget_policy OR BudgetPolicy()

    // Build VerificationLoop using quality_threshold from policy
    v_loop ← VerificationLoop(
        rubric=STANDARD_QUALITY_RUBRIC,
        max_iterations=policy.max_iterations,
        threshold=policy.quality_threshold,
    )

    stop_callback ← make_quality_stop_callback(
        verification_loop=v_loop,
        budget_policy=policy,
        output_key="review_candidate",
    )

    kwargs ← {
        name="review_critic_workflow",
        max_iterations=policy.max_iterations,
        sub_agents=[author_agent, critic_agent],
    }
    kwargs ← _build_loop_agent_kwargs(kwargs, stop_callback)

    RETURN LoopAgent(**kwargs)
  END

PROCEDURE create_iterative_refinement_workflow(settings, budget_policy)
  BEGIN
    policy ← budget_policy OR BudgetPolicy()

    v_loop ← VerificationLoop(
        rubric=STANDARD_QUALITY_RUBRIC,
        max_iterations=policy.max_iterations,
        threshold=policy.quality_threshold,
    )

    stop_callback ← make_quality_stop_callback(
        verification_loop=v_loop,
        budget_policy=policy,
        output_key="refinement_result",
    )

    kwargs ← {
        name="iterative_refinement_workflow",
        max_iterations=policy.max_iterations,
        sub_agents=[drafter_agent, evaluator_agent, refiner_agent],
    }
    kwargs ← _build_loop_agent_kwargs(kwargs, stop_callback)

    RETURN LoopAgent(**kwargs)
  END
```

---

## Example Usage

### Example 1: Wire callback in a workflow factory (Python)

```python
from orchestrator.loops.rubric import STANDARD_QUALITY_RUBRIC
from orchestrator.loops.verification import VerificationLoop
from orchestrator.loops.stop_condition import make_quality_stop_callback
from orchestrator.policies.budget import BudgetPolicy

policy = BudgetPolicy(max_iterations=5, quality_threshold=0.75)

v_loop = VerificationLoop(
    rubric=STANDARD_QUALITY_RUBRIC,
    threshold=policy.quality_threshold,
)

stop_cb = make_quality_stop_callback(
    verification_loop=v_loop,
    budget_policy=policy,
    output_key="review_candidate",
)

# ADK LoopAgent (new API)
loop_agent = LoopAgent(
    name="review_critic_workflow",
    max_iterations=policy.max_iterations,
    sub_agents=[author, critic],
    should_stop_loop=stop_cb,
)
```

### Example 2: Standalone use of `QualityStopCondition` in tests

```python
from orchestrator.loops.stop_condition import QualityStopCondition
from orchestrator.loops.verification import VerificationLoop
from orchestrator.loops.rubric import STANDARD_QUALITY_RUBRIC
from orchestrator.policies.budget import BudgetPolicy

cond = QualityStopCondition(
    verification_loop=VerificationLoop(STANDARD_QUALITY_RUBRIC),
    budget_policy=BudgetPolicy(max_iterations=3),
    output_key="refinement_result",
)

state: dict = {
    "refinement_result": "Final refined text...",
    "loop_iteration": 0,
}
# Simulate high-quality scores
state["loop_criterion_scores"] = {
    "completeness": 0.90, "clarity": 0.85,
    "accuracy": 0.88, "actionability": 0.82,
}
should_stop = cond(state)
assert should_stop is True
assert state["loop_stop_reason"] == "quality_threshold_reached"
assert state["loop_final_score"] >= 0.70
```

### Example 3: Budget exhaustion stops the loop

```python
state = {
    "refinement_result": "Weak output",
    "loop_iteration": 2,      # at limit for max_iterations=3
    "loop_elapsed_ms": 130_000,  # exceeds 120_000 ms cap
}
should_stop = cond(state)
assert should_stop is True
assert state["loop_stop_reason"] == "budget_exhausted"
```

### Example 4: Reading stop diagnostics from `MetricsDTO`

```python
contract = map_adk_execution(session=session, events=events, ...)

stop_reason = contract.metrics.custom.get("loop_stop_reason")
# "quality_threshold_reached" | "budget_exhausted" | None

score = contract.metrics.custom.get("loop_final_score")
iters = contract.metrics.custom.get("loop_iterations_used")
```


---

## Error Handling

### Scenario 1: `output_key` absent from session state

**Condition:** ADK calls `should_stop_loop` before the author/drafter sub-agent has
written its first output (e.g., first tick before any agent completes).

**Response:** `grade_from_state` receives `None` for `raw`; it constructs an empty
responses list and calls `grade([], iteration)`. All criteria score `0.0`, `GraderResult.passed`
is `False`. `BudgetPolicy.should_continue` is still consulted; the loop continues normally.

**Recovery:** No special handling needed; the next tick will find the key populated.

---

### Scenario 2: ADK version does not support `should_stop_loop`

**Condition:** `inspect.signature(LoopAgent.__init__)` does not contain `should_stop_loop`.

**Response:** `_build_loop_agent_kwargs` omits the parameter and logs a `WARNING`-level
message via `logging.getLogger(__name__).warning(...)`. The `LoopAgent` is constructed
with only `max_iterations`, preserving existing behavior.

**Recovery:** Automatic. Upgrade ADK to restore quality-gate behavior.

---

### Scenario 3: `VerificationLoop.grade()` raises unexpectedly

**Condition:** Rubric list is empty, scores are out of range, or a future LLM-judge
integration throws.

**Response:** `QualityStopCondition.__call__` wraps `grade_from_state` in a `try/except
Exception`. On error, it writes `loop_stop_reason = "budget_exhausted"` (conservative:
stop the loop rather than continue blindly) and returns `True`.

**Recovery:** Operator investigates logs; rubric or judge configuration is corrected.

---

### Scenario 4: Session state is not a dict

**Condition:** Future ADK version changes the callback signature.

**Response:** `QualityStopCondition.__call__` checks `isinstance(session_state, dict)`.
If not a dict, it returns `False` (let `max_iterations` govern) and logs a warning.

---

## Testing Strategy

### Unit Testing Approach

- `QualityStopCondition.__call__` unit tests with mocked `VerificationLoop` and
  `BudgetPolicy` — cover: quality pass, budget exhausted, key absent, exception path.
- `VerificationLoop.grade_from_state` unit tests — cover: string value, list value,
  None value, malformed value.
- `BudgetPolicy.should_continue` — existing tests; add regression for `quality_threshold`
  field default and custom values.
- `_build_loop_agent_kwargs` — parametrize against mock `LoopAgent` with and without
  `should_stop_loop` in signature.

### Property-Based Testing Approach

**Property Test Library:** `hypothesis`

- **State mutation idempotency:** For any `session_state`, calling `QualityStopCondition`
  twice with the same inputs always produces consistent `loop_stop_reason`.
- **Monotonic iteration counter:** `loop_iterations_used` is always `old(loop_iteration) + 1`.
- **Score range invariant:** `loop_final_score ∈ [0.0, 1.0]` for any `criterion_scores`
  values drawn from `floats(min_value=0.0, max_value=1.0)`.
- **Budget consistency:** If `should_continue` returns `False`, `__call__` must return `True`.

### Integration Testing Approach

- Create a minimal `LoopAgent` with a stub sub-agent and `QualityStopCondition`.
  Drive it with synthetic session states; assert iteration count is below `max_iterations`
  when quality threshold is reached on iteration 2.
- Verify `contract.metrics.custom["loop_stop_reason"]` is populated correctly through
  the full `map_adk_execution` path.

---

## Security Considerations

- `session_state` is an ADK-managed dict; no user-controlled strings are evaluated as code.
- `QualityStopCondition` writes only well-typed primitive values to state; no injection risk.
- In future LLM-judge integration, scores returned from the judge must be clamped to
  `[0.0, 1.0]` before use — already enforced by `grade()`.

---

## Performance Considerations

- `QualityStopCondition.__call__` is synchronous and O(n) in the number of rubric criteria
  (4 for `STANDARD_QUALITY_RUBRIC`). No I/O, no model calls in the current implementation.
- `dataclasses.asdict(result)` performs a shallow copy; negligible overhead.
- The callback is invoked once per loop tick (after all sub-agents complete), so latency
  impact is bounded by rubric size × number of iterations.

---

## Dependencies

| Module | Change | Reason |
|---|---|---|
| `loops/stop_condition.py` | **New file** | Houses `QualityStopCondition` and factory |
| `loops/verification.py` | **Add method** `grade_from_state` | State-aware grading helper |
| `policies/budget.py` | **Add field** `quality_threshold` | Unified policy object |
| `agents/workflows.py` | **Update** two factory functions | Wire stop callback to LoopAgents |
| `mapping/adk.py` | **Update** `map_adk_execution` | Expose stop diagnostics in MetricsDTO |
| `loops/__init__.py` | **Update** exports | Export `QualityStopCondition`, `make_quality_stop_callback` |
| `orchestrator.adk_compat` | No change | `load_symbol` already available |
| `google-adk` | Runtime dep (existing) | `LoopAgent.should_stop_loop` parameter |
| `hypothesis` | Dev dep (existing) | Property-based tests |

---

## Correctness Properties

The following properties must hold for every execution of the smart stop condition:

### Property 1: Termination guarantee

For any finite `max_iterations` in `BudgetPolicy`, the `LoopAgent` always terminates —
either because `GraderResult.passed` becomes `True`, or because
`BudgetPolicy.should_continue` returns `False`, or because `LoopAgent` itself exhausts
`max_iterations`. The callback never prevents termination.

**Validates: Requirements 8.1**

### Property 2: Score range invariant

For all inputs, `GraderResult.overall_score ∈ [0.0, 1.0]`.
Formally: `∀ scores ∈ [0,1]^n, ∀ weights ∈ ℝ₊^n → weighted_average(scores, weights) ∈ [0,1]`.

**Validates: Requirements 8.2**

### Property 3: Stop reason completeness

Whenever `QualityStopCondition.__call__` returns `True`,
`session_state["loop_stop_reason"]` is set to either `"quality_threshold_reached"` or
`"budget_exhausted"`. It is never set when the callback returns `False`.

**Validates: Requirements 1.5, 1.6**

### Property 4: Monotonic iteration counter

For successive calls on the same session state,
`session_state["loop_iterations_used"]` strictly increases by exactly 1 per call.

**Validates: Requirements 1.7, 1.8**

### Property 5: Budget consistency

`should_continue(iterations, model_calls, elapsed_ms) = False` implies
`QualityStopCondition.__call__(state) = True` when `loop_iteration` equals `iterations`.
That is, budget exhaustion always stops the loop.

**Validates: Requirements 1.4, 8.6**

### Property 6: Quality threshold consistency

If `GraderResult.passed = True` then `GraderResult.overall_score ≥ verification_loop.threshold`.
If `GraderResult.passed = False` then `GraderResult.overall_score < verification_loop.threshold`.

**Validates: Requirements 8.3, 8.4**

### Property 7: Standalone usability

`VerificationLoop.grade()` and `VerificationLoop.grade_from_state()` produce identical
results when given equivalent inputs, regardless of whether ADK is installed. No ADK
import is required to construct or call a `VerificationLoop`.

**Validates: Requirements 3.6, 8.5**

### Property 8: Graceful degradation

If `LoopAgent` does not accept `should_stop_loop`, the workflow still constructs and
runs successfully with `max_iterations`-only termination. No exception is raised; the
degradation is logged at WARNING level.

**Validates: Requirements 5.3, 5.6**
