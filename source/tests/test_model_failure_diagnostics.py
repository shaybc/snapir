"""Check retry causes, retained output, and redacted failure evidence offline."""

import logging

import pytest

from cli.diagnostics import console_diagnostics
from models.pipeline_configuration import PipelineConfiguration
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.diagnostics import run_model_diagnostics
from runtime.model_execution.error_details import sanitize_diagnostic, print_failure_traceback


@pytest.mark.parametrize("message", [
    "Request failed https://user:pass-secret@host.test/v1?key=query-secret&other=value-secret",
    "headers={'Authorization': 'Bearer bearer-secret', 'x-api-key': 'header-secret'}",
    'body={"api_key": "body-secret", "access_token": "token-secret"}',
    "password=plain-secret client_secret=client-secret",
])
def test_credentials_are_redacted(message):
    output = sanitize_diagnostic(message)
    assert "secret" not in output.replace("client_secret", "")
    assert "[REDACTED]" in output


@pytest.mark.parametrize("verbose", [False, True])
def test_retries_keep_cause_and_safe_run_log(tmp_path, monkeypatch, capsys, verbose):
    monkeypatch.setattr("runtime.model_execution.adk_executor.require_model_readiness", lambda *_: None)
    executor = AdkExecutor(PipelineConfiguration(max_model_attempts=2))
    attempts = []
    async def fail(*_):
        attempts.append(1)
        raise RuntimeError("503 Service unavailable https://host.test/v1?api_key=query-secret Authorization: Bearer bearer-secret")
    monkeypatch.setattr(executor, "_execute", fail)
    original_handlers = logging.getLogger("runtime").handlers[:]
    with console_diagnostics(verbose), run_model_diagnostics(tmp_path):
        with pytest.raises(RuntimeError, match="after 2 attempts: 503 Service unavailable") as failure:
            executor.execute("instruction", "payload")
        if verbose:
            print_failure_traceback(failure.value)
    output = capsys.readouterr()
    assert attempts == [1, 1]
    assert "503 Service unavailable" in output.err
    assert ("Traceback" in output.err) == verbose
    assert "query-secret" not in output.err and "bearer-secret" not in output.err
    saved = (tmp_path / "logs/model_execution.log").read_text(encoding="utf-8")
    assert "Traceback" in saved and "503 Service unavailable" in saved
    assert "query-secret" not in saved and "bearer-secret" not in saved
    assert logging.getLogger("runtime").handlers == original_handlers


def test_resume_warning_survives_failure_and_return_to_menu(monkeypatch, tmp_path, capsys):
    from cli.main import main
    commands = iter(["resume", "exit"])
    def complete(args, _):
        args.command = next(commands)
        if args.command == "exit":
            output = capsys.readouterr().out
            assert "Provider warning before failure" in output
            assert "Migration error: Model execution failed after 2 attempts: 503 Service unavailable" in output
    monkeypatch.setattr("cli.main.complete_arguments", complete)
    monkeypatch.setattr("cli.main.select_resume_run", lambda: tmp_path / "existing")
    monkeypatch.setattr("cli.main.clear_screen", lambda: pytest.fail("Erased action output"))
    def fail(*_):
        print("Provider warning before failure")
        raise RuntimeError("Model execution failed after 2 attempts: 503 Service unavailable")
    monkeypatch.setattr("cli.main.resume_pipeline", fail)
    assert main([]) == 0


def test_executor_supplies_literal_instruction_provider(monkeypatch):
    import asyncio
    from google.adk.agents import LlmAgent
    prompt = "Literal source: on{N}Return; class Example { }"
    captured = []
    monkeypatch.setattr("runtime.model_execution.adk_executor.require_model_readiness", lambda *_: None)
    monkeypatch.setenv("GOOGLE_API_KEY", "offline-test-key")
    def runner(**kwargs):
        agent = kwargs["agent"]
        assert isinstance(agent, LlmAgent)
        assert callable(agent.instruction)
        captured.append(agent.instruction(None))
        raise RuntimeError("offline runner boundary")
    monkeypatch.setattr("google.adk.runners.Runner", runner)
    with pytest.raises(RuntimeError, match="offline runner boundary"):
        asyncio.run(AdkExecutor(PipelineConfiguration())._execute(prompt, "{}"))
    assert captured == [prompt]


def test_component_context_survives_callbacks_and_resets(monkeypatch, caplog):
    from runtime.model_execution.component_progress import component_suffix
    from runtime.model_execution.progress import before_model, after_model
    monkeypatch.setattr("runtime.model_execution.adk_executor.require_model_readiness", lambda *_: None)
    executor = AdkExecutor(PipelineConfiguration())
    executor.component_label = "Component 3/10: Example"
    async def respond(*_):
        assert component_suffix() == " [Component 3/10: Example]"
        before_model(None, None)
        after_model(None, None)
        return "response"
    monkeypatch.setattr(executor, "_execute", respond)
    with caplog.at_level(logging.INFO):
        assert executor.execute("instruction", "payload") == "response"
    assert component_suffix() == ""
    messages = [record.getMessage() for record in caplog.records if record.name.startswith("runtime.model_execution") and not getattr(record, "model_interaction_boundary", None)]
    assert len(messages) == 4
    assert all("Component 3/10: Example" in message for message in messages)


@pytest.mark.parametrize("fails", [False, True])
def test_model_interaction_console_boundaries_close_on_failure(monkeypatch, capsys, fails):
    monkeypatch.setattr("runtime.model_execution.adk_executor.require_model_readiness", lambda *_: None)
    executor = AdkExecutor(PipelineConfiguration(max_model_attempts=1))
    async def respond(*_):
        if fails:
            raise RuntimeError("provider failure")
        return "response"
    monkeypatch.setattr(executor, "_execute", respond)
    with console_diagnostics(False):
        if fails:
            with pytest.raises(RuntimeError, match="provider failure"):
                executor.execute("instruction", "payload")
        else:
            executor.execute("instruction", "payload")
    output = capsys.readouterr().err
    separator = "-" * 68
    assert output.startswith("\n" + separator + "\nINFO: Model execution attempt")
    assert output.endswith(separator + "\n\n")
    assert output.count(separator) == 2
