"""Gemini model construction with bounded transient-error retries."""

from __future__ import annotations

from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.config import OrchestratorSettings

TRANSIENT_HTTP_STATUS_CODES = [408, 429, 500, 502, 503, 504]


def create_gemini_model(settings: OrchestratorSettings) -> Any:
    """Create an ADK Gemini model with request-level exponential backoff.

    Retrying at the model client boundary avoids replaying an entire workflow,
    which could duplicate tool calls or other agent side effects.
    """

    Gemini = load_symbol("google.adk.models", "Gemini")
    HttpRetryOptions = load_symbol("google.genai.types", "HttpRetryOptions")
    return Gemini(
        model=settings.model,
        retry_options=HttpRetryOptions(
            attempts=settings.model_retry_attempts,
            initial_delay=settings.model_retry_initial_delay_seconds,
            max_delay=settings.model_retry_max_delay_seconds,
            exp_base=settings.model_retry_exponential_base,
            jitter=settings.model_retry_jitter_seconds,
            http_status_codes=TRANSIENT_HTTP_STATUS_CODES,
        ),
    )
