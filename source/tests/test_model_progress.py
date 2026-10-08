"""Verify visible model milestones and credential-safe verbose details offline."""

import asyncio

import httpx
import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from cli.diagnostics import console_diagnostics
from models.pipeline_configuration import PipelineConfiguration
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.progress import before_model, after_model, request_headers, response_headers, wait_with_progress


@pytest.mark.parametrize("verbose", [False, True])
def test_model_content_and_headers_only_visible_in_verbose(verbose, capsys, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "private-key-value")
    request = LlmRequest(model="test-model", contents=[types.Content(parts=[types.Part(text="request-content")])])
    response = LlmResponse(content=types.Content(parts=[types.Part(text="response-content")]))
    http_request = httpx.Request("POST", "https://provider.test/model?key=private-key-value",
                                 headers={"x-goog-api-key": "private-key-value", "Cookie": "private-cookie"})
    http_response = httpx.Response(200, headers={"set-cookie": "private-cookie", "x-request-id": "safe-id"})
    with console_diagnostics(verbose):
        before_model(None, request)
        after_model(None, response)
        asyncio.run(request_headers(http_request))
        asyncio.run(response_headers(http_response))
    output = capsys.readouterr().err
    assert "Sending model request" in output and "Provider response received" in output
    assert ("request-content" in output) == verbose
    assert ("response-content" in output) == verbose
    assert ("safe-id" in output) == verbose
    assert "private-key-value" not in output and "private-cookie" not in output


def test_attempt_and_completion_visible_without_verbose(monkeypatch, capsys):
    monkeypatch.setattr("runtime.model_execution.adk_executor.require_model_readiness", lambda *_: None)
    executor = AdkExecutor(PipelineConfiguration())
    async def complete(*_):
        return "result"
    monkeypatch.setattr(executor, "_execute", complete)
    with console_diagnostics(False):
        assert executor.execute("instruction", "payload") == "result"
    output = capsys.readouterr().err
    assert "attempt 1/" in output and "completed in" in output
    assert "instruction" not in output


def test_wait_retains_timeout_and_cancels_request():
    cancelled = []
    async def never_finishes():
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(True)
    with pytest.raises(TimeoutError):
        asyncio.run(wait_with_progress(never_finishes(), 0.01))
    assert cancelled == [True]
