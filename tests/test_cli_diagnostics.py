"""Verify CLI diagnostics without remote model execution."""

import logging
from types import SimpleNamespace

import pytest

from cli.main import main
from cli.diagnostics import console_diagnostics


@pytest.mark.parametrize("flag", [None, "--verbose", "-v"])
def test_handled_failure_controls_upstream_traceback(flag, monkeypatch, capsys):
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root="unused"))
    monkeypatch.setattr("cli.main.complete_arguments", lambda *_: None)
    monkeypatch.setattr("cli.main.complete_run_selection", lambda *_: None)

    def fail(*_):
        try:
            raise ValueError("Please provide an API key")
        except ValueError:
            logging.getLogger("google_adk.google.adk.workflow._node_runner").exception("Node execution failed")
            logging.getLogger("runtime.model_execution").debug("Diagnostic detail")
            raise

    monkeypatch.setattr("cli.main.resume_pipeline", fail)
    arguments = ["resume", "--config", "supplied.yaml", "--run-id", "existing"]
    if flag:
        arguments.append(flag)
    assert main(arguments) == 1
    output = capsys.readouterr()
    assert "Migration error: Please provide an API key" in output.out
    assert "Node execution failed" in output.err
    assert ("Traceback (most recent call last)" in output.err) == bool(flag)
    assert ("Diagnostic detail" in output.err) == bool(flag)


def test_help_describes_verbose(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    assert "--verbose" in capsys.readouterr().out


def test_diagnostics_preserve_file_exception_and_restore_logging(tmp_path, capsys):
    logger = logging.getLogger("google_adk")
    original = (logger.level, logger.propagate, logger.handlers[:])
    file_handler = logging.FileHandler(tmp_path / "diagnostics.log")
    logger.addHandler(file_handler)
    try:
        with console_diagnostics(False):
            try:
                raise RuntimeError("Evidence retained")
            except RuntimeError:
                logger.exception("Failure")
        assert "Traceback" not in capsys.readouterr().err
        assert "Traceback" in (tmp_path / "diagnostics.log").read_text()
        assert (logger.level, logger.propagate, logger.handlers) == (
            original[0], original[1], original[2] + [file_handler])
    finally:
        logger.removeHandler(file_handler)
        file_handler.close()


@pytest.mark.parametrize("arguments", [[], ["start", "--config", "supplied.yaml", "--run-id", "supplied"]])
def test_verbose_preserves_argument_completion(arguments, monkeypatch, tmp_path):
    def complete(args, _):
        assert args.verbose
        if arguments:
            assert (args.command, args.config, args.run_id) == ("start", "supplied.yaml", "supplied")
        else:
            assert args.command is None
            args.command, args.config, args.run_id = "start", "selected.yaml", "selected"
    monkeypatch.setattr("cli.main.complete_arguments", complete)
    monkeypatch.setattr("cli.main.complete_run_selection", lambda *_: None)
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    calls = []
    monkeypatch.setattr("cli.main.run_pipeline", lambda profile, run_id: calls.append(run_id) or tmp_path)
    assert main(arguments + ["--verbose"]) == 0
    assert calls == ["supplied" if arguments else "selected"]


@pytest.mark.parametrize("verbose", [False, True])
def test_resume_failure_still_persists_failed_status(verbose, tmp_path, monkeypatch, capsys):
    from models.pipeline_configuration import PipelineConfiguration
    from tests.test_migration_planning import run_config
    from tools.state_store_tools.db import create_all_tables, get_connection
    from tools.state_store_tools.runs import get_run, upsert_run

    state = tmp_path / "run-1" / "state"
    state.mkdir(parents=True)
    profile = PipelineConfiguration(source_root="source", mapper_jar="mapper", output_root=str(tmp_path),
                                    channels=["INTERNET"])
    (state / "profile.json").write_text(profile.model_dump_json())
    database = state / "migration.db"
    with get_connection(str(database)) as conn:
        create_all_tables(conn)
        upsert_run(conn, run_id="run-1", run_mode="single_channel", status="paused",
                   current_phase="planning_inputs_ready", run_config=run_config())
    conn.close()
    monkeypatch.setattr("cli.main.load_configuration", lambda _: profile)
    monkeypatch.setattr("runtime.checkpoints.get_operations_for_planning", lambda *_: [])

    def fail(*_):
        raise ValueError("Please provide an API key")

    monkeypatch.setattr("runtime.checkpoints.prepare_plan", fail)
    arguments = ["resume", "--config", "supplied.yaml", "--run-id", "run-1"]
    assert main(arguments + (["--verbose"] if verbose else [])) == 1
    with get_connection(str(database)) as conn:
        run = get_run(conn, "run-1")
        assert (run["status"], run["current_phase"]) == ("failed", "planning_failed")
    conn.close()
    assert ("Traceback" in capsys.readouterr().err) == verbose
