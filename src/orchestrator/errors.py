"""Preserve actionable causes hidden by ADK dynamic-node wrappers."""

from __future__ import annotations


def execution_error_message(error: BaseException) -> str:
    messages = []
    seen = set()
    while isinstance(error, BaseException) and id(error) not in seen:
        seen.add(id(error))
        message = str(error)
        if message and message not in messages:
            messages.append(message)
        error = getattr(error, "error", None) or error.__cause__
    return ": ".join(messages)
