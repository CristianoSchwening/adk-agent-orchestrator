"""Small budget policy placeholder for phase 1 and future workflow callbacks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPolicy:
    """Execution budget guard to be wired into ADK callbacks in phase 2."""

    max_iterations: int = 3
    max_model_calls: int = 12
    max_elapsed_ms: int = 120_000

    def should_continue(self, *, iterations: int, model_calls: int, elapsed_ms: int) -> bool:
        """Return whether an execution can proceed under the configured budget."""

        return (
            iterations < self.max_iterations
            and model_calls < self.max_model_calls
            and elapsed_ms < self.max_elapsed_ms
        )
