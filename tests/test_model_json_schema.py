from __future__ import annotations

import asyncio

import pytest

from orchestrator.adk_compat import is_adk_installed

pytestmark = pytest.mark.skipif(not is_adk_installed(), reason="google-adk is not installed")


@pytest.mark.parametrize("stream", [False, True])
def test_dict_schema_serializes_without_mutating_request(monkeypatch, stream):
    from google import genai
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from google.genai import models

    from orchestrator.agents.context_intelligence import CONTEXT_PACKAGE_DRAFT_SCHEMA
    from orchestrator.config import OrchestratorSettings
    from orchestrator.model import create_gemini_model

    request = LlmRequest(model="gemini-2.5-flash")
    request.set_output_schema(CONTEXT_PACKAGE_DRAFT_SCHEMA)
    original = request.model_copy(deep=True)
    with genai.Client(api_key="offline-test-only") as client:
        def serialize(req):
            return models._GenerateContentParameters_to_mldev(
                client._api_client, {"model": req.model, "config": req.config}
            )

        with pytest.raises(ValueError, match="additionalProperties"):
            serialize(request.model_copy(deep=True))

        async def generate(self, req, stream=False):
            assert stream is expected_stream
            config = serialize(req)["generationConfig"]
            assert config["responseJsonSchema"] == CONTEXT_PACKAGE_DRAFT_SCHEMA
            assert "responseSchema" not in config
            req.config.response_json_schema["description"] = "mutation by provider"
            yield "validated"

        expected_stream = stream
        monkeypatch.setattr(Gemini, "generate_content_async", generate)
        model = create_gemini_model(OrchestratorSettings(
            model="gemini-2.5-flash", fallback_model="gemini-2.5-flash-lite"
        ))

        async def exercise():
            for provider in (model.primary, model.fallback):
                assert [r async for r in provider.generate_content_async(
                    request, stream=stream
                )] == ["validated"]
                assert request == original

        asyncio.run(exercise())


@pytest.mark.parametrize("kind", ["none", "typed", "json", "conflict"])
def test_other_schema_modes(monkeypatch, kind):
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from pydantic import BaseModel

    from orchestrator.model import _json_schema_gemini_class

    class Answer(BaseModel):
        answer: str

    request = LlmRequest(model="gemini-2.5-flash")
    if kind == "typed":
        request.config.response_schema = Answer
    if kind in {"json", "conflict"}:
        request.config.response_json_schema = {"type": "object"}
    if kind == "conflict":
        request.config.response_schema = {"type": "object"}

    async def generate(self, req, stream=False):
        assert req == request
        yield "unchanged"

    monkeypatch.setattr(Gemini, "generate_content_async", generate)

    async def exercise():
        model = _json_schema_gemini_class()(model=request.model)
        return [r async for r in model.generate_content_async(request)]

    if kind == "conflict":
        with pytest.raises(ValueError, match="Both response_schema"):
            asyncio.run(exercise())
    else:
        assert asyncio.run(exercise()) == ["unchanged"]


@pytest.mark.parametrize("mode, expected_calls", [("recover", 2), ("exhaust", 3), ("partial", 1)])
def test_transport_retry_is_bounded_and_never_replays_output(monkeypatch, mode, expected_calls):
    from aiohttp import ClientPayloadError
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest

    from orchestrator import model as module

    calls = []
    async def generate(self, req, stream=False):
        calls.append(req)
        if mode == "partial":
            yield "partial"
        if mode != "recover" or len(calls) == 1:
            raise ClientPayloadError("truncated response")
        yield "complete"

    async def sleep(delay):
        pass

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    async def exercise():
        model = module._json_schema_gemini_class()(model="gemini-2.5-flash")
        return [r async for r in model.generate_content_async(LlmRequest())]

    if mode == "recover":
        assert asyncio.run(exercise()) == ["complete"]
    else:
        with pytest.raises(ClientPayloadError):
            asyncio.run(exercise())
    assert len(calls) == expected_calls

def test_runner_returns_failed_contract_with_completed_work(monkeypatch):
    from types import SimpleNamespace

    from orchestrator.config import OrchestratorSettings
    from orchestrator.runner import bootstrap as module

    session = SimpleNamespace(id="test", state={"task_run": {"tasks": [
        {"task_id": "TASK-001", "status": "completed", "result": "Saved research"}
    ]}})
    async def get_session(*args):
        return session
    async def run_async(**kwargs):
        raise RuntimeError("transport exhausted")
        yield
    runtime = SimpleNamespace(
        settings=OrchestratorSettings(workspace_enabled=False),
        runner=SimpleNamespace(run_async=run_async), selected_workflow="parallel"
    )
    monkeypatch.setattr(module, "build_runtime", lambda *args, **kwargs: runtime)
    monkeypatch.setattr(module, "_create_session", get_session)
    monkeypatch.setattr(module, "_get_session", get_session)
    monkeypatch.setattr(module, "_persist_generated_task_plan", lambda *args: None)
    contract = asyncio.run(module.run_once_contract("test"))
    assert contract.task.status == "failed"
    assert "Saved research" in contract.task.final_response
    assert contract.metrics.error_count == 1
