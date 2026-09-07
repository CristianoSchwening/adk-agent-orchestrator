"""Gemini model construction with bounded transient-error retries."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from threading import Lock
from typing import Any

from orchestrator.adk_compat import load_symbol
from orchestrator.config import ModelRole, OrchestratorSettings

TRANSIENT_HTTP_STATUS_CODES = [408, 429, 500, 502, 503, 504]
_OPEN_DAILY_QUOTA_CIRCUITS: set[str] = set()
_CIRCUIT_LOCK = Lock()


@lru_cache(maxsize=1)
def _json_schema_gemini_class() -> type[Any]:
    Gemini = load_symbol("google.adk.models", "Gemini")

    class JsonSchemaGemini(Gemini):
        async def generate_content_async(self, llm_request: Any, stream: bool = False) -> Any:
            # Raw JSON schemas must use the JSON Schema transport. The legacy
            # response_schema converter rejects additionalProperties on MLDev.
            config = llm_request.config
            if config is not None and isinstance(config.response_schema, dict):
                if config.response_json_schema is not None:
                    raise ValueError("Both response_schema and response_json_schema are set")
                llm_request = llm_request.model_copy(deep=True)
                llm_request.config.response_json_schema = llm_request.config.response_schema
                llm_request.config.response_schema = None
            for attempt in range(3):
                yielded = False
                try:
                    request = llm_request.model_copy(deep=True)
                    async for response in super().generate_content_async(request, stream=stream):
                        yielded = True
                        yield response
                    return
                except Exception as exc:
                    if not is_transport_error(exc) or yielded or attempt == 2:
                        raise
                    await asyncio.sleep(0.5 * 2**attempt)

    return JsonSchemaGemini


def _gemini_client(settings: OrchestratorSettings, model: str) -> Any:
    HttpRetryOptions = load_symbol("google.genai.types", "HttpRetryOptions")
    return _json_schema_gemini_class()(
        model=model,
        retry_options=HttpRetryOptions(
            attempts=settings.model_retry_attempts,
            initial_delay=settings.model_retry_initial_delay_seconds,
            max_delay=settings.model_retry_max_delay_seconds,
            exp_base=settings.model_retry_exponential_base,
            jitter=settings.model_retry_jitter_seconds,
            http_status_codes=TRANSIENT_HTTP_STATUS_CODES,
        ),
    )


def _exception_chain_text(exc: BaseException) -> str:
    messages: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        messages.append(str(current))
        current = current.__cause__ or current.__context__
    return "\n".join(messages).lower()


def _fallback_reason(exc: BaseException) -> str | None:
    text = _exception_chain_text(exc)
    if "429" in text or "resource_exhausted" in text:
        if (
            "generaterequestsperday" in text
            or "requestsperday" in text
            or "requests per day" in text
        ):
            return "daily_quota_exhausted"
        return "rate_limit_exhausted"
    if "503" in text or "unavailable" in text:
        return "provider_unavailable"
    return None


def _is_daily_circuit_open(model: str) -> bool:
    with _CIRCUIT_LOCK:
        return model in _OPEN_DAILY_QUOTA_CIRCUITS


def _open_daily_circuit(model: str) -> None:
    with _CIRCUIT_LOCK:
        _OPEN_DAILY_QUOTA_CIRCUITS.add(model)


def reset_model_fallback_circuits() -> None:
    """Reset in-process quota circuits; intended for tests and controlled operations."""

    with _CIRCUIT_LOCK:
        _OPEN_DAILY_QUOTA_CIRCUITS.clear()


@lru_cache(maxsize=1)
def _fallback_model_class() -> type[Any]:
    BaseLlm = load_symbol("google.adk.models", "BaseLlm")

    class FallbackGeminiModel(BaseLlm):
        """Delegate one model turn to a fallback without replaying the workflow."""

        primary: Any
        fallback: Any
        role: str
        fallback_model: str

        async def generate_content_async(self, llm_request: Any, stream: bool = False) -> Any:
            reason = (
                "daily_quota_circuit_open"
                if _is_daily_circuit_open(self.model)
                else None
            )
            if reason is None:
                yielded = False
                try:
                    llm_request.model = self.model
                    async for response in self.primary.generate_content_async(
                        llm_request,
                        stream=stream,
                    ):
                        yielded = True
                        _annotate_model_routing(
                            response,
                            role=self.role,
                            requested_model=self.model,
                            used_model=self.model,
                            fallback_used=False,
                            fallback_reason=None,
                        )
                        yield response
                    return
                except Exception as exc:
                    reason = _fallback_reason(exc)
                    if yielded or reason is None:
                        raise
                    if reason == "daily_quota_exhausted":
                        _open_daily_circuit(self.model)

            llm_request.model = self.fallback_model
            async for response in self.fallback.generate_content_async(
                llm_request,
                stream=stream,
            ):
                _annotate_model_routing(
                    response,
                    role=self.role,
                    requested_model=self.model,
                    used_model=self.fallback_model,
                    fallback_used=True,
                    fallback_reason=reason,
                )
                yield response

    FallbackGeminiModel.__name__ = "FallbackGeminiModel"
    return FallbackGeminiModel


def _annotate_model_routing(
    response: Any,
    *,
    role: str,
    requested_model: str,
    used_model: str,
    fallback_used: bool,
    fallback_reason: str | None,
) -> None:
    metadata = dict(getattr(response, "custom_metadata", None) or {})
    metadata["model_routing"] = {
        "role": role,
        "requested_model": requested_model,
        "used_model": used_model,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
    }
    response.custom_metadata = metadata


def _with_fallback(primary: Any, fallback: Any, *, role: ModelRole) -> Any:
    model_class = _fallback_model_class()
    return model_class(
        model=primary.model,
        primary=primary,
        fallback=fallback,
        role=role,
        fallback_model=fallback.model,
    )


def create_gemini_model(
    settings: OrchestratorSettings,
    *,
    role: ModelRole = "worker",
) -> Any:
    """Create an ADK Gemini model with request-level exponential backoff.

    Retrying at the model client boundary avoids replaying an entire workflow,
    which could duplicate tool calls or other agent side effects.
    """

    primary_model = settings.model_for(role)
    primary = _gemini_client(settings, primary_model)
    fallback_model = settings.fallback_model
    if fallback_model is None or fallback_model == primary_model:
        return primary
    return _with_fallback(
        primary,
        _gemini_client(settings, fallback_model),
        role=role,
    )


def is_transport_error(exc: BaseException) -> bool:
    """Recognize interrupted responses, including ADK's wrapped node errors."""
    from aiohttp import ClientConnectionError, ClientPayloadError

    pending = [exc]
    seen = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, (ClientConnectionError, ClientPayloadError, ConnectionResetError)):
            return True
        for nested in (current.__cause__, current.__context__, getattr(current, "error", None)):
            if isinstance(nested, BaseException):
                pending.append(nested)
    return False
