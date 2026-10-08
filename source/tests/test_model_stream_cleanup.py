"""Verify ADK streams finish or close in their consuming asynchronous context."""

import asyncio
from contextvars import ContextVar
from types import SimpleNamespace

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.progress import wait_with_progress


def executor_with_stream(monkeypatch, stream):
    """Substitute local ADK collaborators so no provider is contacted."""
    import google.adk.agents
    import google.adk.runners
    import google.adk.sessions
    import google.adk.models.lite_llm

    monkeypatch.setenv("STREAM_TEST_KEY", "test-only-key")
    monkeypatch.setattr("runtime.model_execution.adk_executor.require_model_readiness", lambda *_: None)
    monkeypatch.setattr(google.adk.agents, "LlmAgent", lambda **_: object())
    monkeypatch.setattr(google.adk.models.lite_llm, "LiteLlm", lambda **_: object())
    async def create_session(**_):
        return SimpleNamespace(id="local-session")
    monkeypatch.setattr(google.adk.sessions, "InMemorySessionService",
                        lambda: SimpleNamespace(create_session=create_session))
    monkeypatch.setattr(google.adk.runners, "Runner",
                        lambda **_: SimpleNamespace(run_async=lambda **_: stream()))
    return AdkExecutor(PipelineConfiguration(model_provider="litellm",
                        model_api_key_environment="STREAM_TEST_KEY"))


def final_event():
    """Represent a final model answer without SDK transport objects."""
    return SimpleNamespace(is_final_response=lambda: True,
                           content=SimpleNamespace(parts=[SimpleNamespace(text="saved-answer")]))


def test_stream_finishes_after_final_answer_in_same_context(monkeypatch):
    context = ContextVar("test_stream")
    stages = []
    async def stream():
        token = context.set("active")
        try:
            yield final_event()
            stages.append("drained")
        finally:
            context.reset(token)
            stages.append("closed")
    executor = executor_with_stream(monkeypatch, stream)
    assert asyncio.run(executor._execute("instruction", "payload")) == "saved-answer"
    assert stages == ["drained", "closed"]


@pytest.mark.parametrize("interruption", ["timeout", "error"])
def test_interrupted_stream_closes_in_consuming_task(monkeypatch, interruption):
    context = ContextVar("test_interrupted_stream")
    stages = []
    async def stream():
        token = context.set("active")
        try:
            yield final_event()
            if interruption == "error":
                raise RuntimeError("stream failure")
            await asyncio.sleep(60)
        finally:
            context.reset(token)
            stages.append("closed")
    executor = executor_with_stream(monkeypatch, stream)
    expected = TimeoutError if interruption == "timeout" else RuntimeError
    with pytest.raises(expected):
        asyncio.run(wait_with_progress(executor._execute("instruction", "payload"), 0.05))
    assert stages == ["closed"]
