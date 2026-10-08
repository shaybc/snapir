"""Verify saved-run Resume selection and menu return without model execution."""

import sqlite3
from types import SimpleNamespace

import pytest

from cli import interactive
from cli.main import main
from cli.status_discovery import discover_status_runs


def saved_run(root, run_id="existing", phase="planning_failed", *, profile=True):
    directory = root / run_id
    state = directory / "state"
    state.mkdir(parents=True)
    if profile:
        (state / "profile.json").write_text('{"model_name": "saved-model"}')
    with sqlite3.connect(state / "migration.db") as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT, status TEXT, current_phase TEXT)")
        conn.execute("INSERT INTO runs VALUES (?, 'failed', ?)", (run_id, phase))
    return directory


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(interactive, "project_root", lambda: tmp_path)
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)
    monkeypatch.setattr("cli.status_discovery.constants.OUTPUT_ROOT", "work/migration_runs")
    monkeypatch.setattr("cli.main.load_configuration", lambda *_: pytest.fail("Loaded original YAML"))
    monkeypatch.setattr("cli.main.complete_run_selection", lambda *_: pytest.fail("Used original config"))
    return tmp_path


def test_resumable_filter_preserves_status_choices(project):
    root = project / "work/migration_runs"
    supported = saved_run(root, "supported", "planning_failed")
    saved_run(root, "unsupported", "paused_awaiting_operator")
    saved_run(root, "missing-profile", profile=False)
    assert len(discover_status_runs(project)) == 3
    options = discover_status_runs(project, resumable_only=True)
    assert [path for path, _ in options] == [str(supported)]
    assert "failed" in options[0][1] and "planning_failed" in options[0][1]


def test_resume_uses_selected_saved_run_and_shows_updated_checkpoint(project, monkeypatch, capsys):
    configs = project / "configs"
    configs.mkdir()
    (configs / "unusable.yaml").write_text("output_root: ../alternate\nsource_root: missing\nmapper_jar: missing\n")
    directory = saved_run(project / "alternate")
    choices = iter(["resume", str(directory), "exit"])
    events = []
    def select(title, options):
        assert title != "Select a configuration"
        selected = next(choices)
        if selected == "exit":
            output = capsys.readouterr().out
            assert "Resume returned for run: existing" in output
            assert "Saved status: paused; checkpoint: gate_1_pending" in output
            assert "View run status" in output
            assert "completed" not in output.lower()
            assert events[-1] == "resume"
        return selected
    monkeypatch.setattr(interactive, "select_option", select)
    calls = []
    def resume(root, run_id):
        calls.append((root, run_id))
        assert (directory / "state/profile.json").read_text() == '{"model_name": "saved-model"}'
        with sqlite3.connect(directory / "state/migration.db") as conn:
            conn.execute("UPDATE runs SET status='paused', current_phase='gate_1_pending'")
        events.append("resume")
        return directory
    monkeypatch.setattr("cli.main.resume_pipeline", resume)
    monkeypatch.setattr("cli.main.clear_screen", lambda: events.append("clear"))
    assert main(["--config", "ignored.yaml", "--run-id", "ignored"]) == 0
    assert calls == [(str(directory.parent), "existing")]


def test_blocked_dependency_resume_offers_report_then_returns_to_menu(project, monkeypatch):
    directory = saved_run(project / "work/migration_runs", phase="closures_blocked")
    with sqlite3.connect(directory / "state/migration.db") as conn:
        conn.execute("UPDATE runs SET status='blocked'")
    choices = iter(["resume", str(directory), "exit"])
    monkeypatch.setattr(interactive, "select_option", lambda *_: next(choices))
    monkeypatch.setattr("cli.main.resume_pipeline", lambda *_: directory)
    offered = []
    monkeypatch.setattr("cli.main.offer_dependency_closure_report", lambda path: offered.append(path))
    assert main([]) == 0
    assert offered == [directory]


@pytest.mark.parametrize("verbose", [False, True])
def test_handled_resume_failure_returns_menu_and_preserves_failed_checkpoint(project, monkeypatch, capsys, verbose):
    directory = saved_run(project / "work/migration_runs", phase="planning_inputs_ready")
    choices = iter(["resume", str(directory), "exit"])
    calls = []
    def select(title, options):
        selected = next(choices)
        if selected == "exit":
            output = capsys.readouterr()
            assert "Migration error: Please provide an API key" in output.out
            assert "Resume returned" not in output.out
            assert ("Traceback" in output.err) == verbose
        return selected
    monkeypatch.setattr(interactive, "select_option", select)
    def fail(root, run_id):
        calls.append(run_id)
        with sqlite3.connect(directory / "state/migration.db") as conn:
            conn.execute("UPDATE runs SET status='failed', current_phase='planning_failed'")
        raise ValueError("Please provide an API key")
    monkeypatch.setattr("cli.main.resume_pipeline", fail)
    assert main(["--verbose"] if verbose else []) == 0
    assert calls == ["existing"]
    with sqlite3.connect(directory / "state/migration.db") as conn:
        assert conn.execute("SELECT status, current_phase FROM runs").fetchone() == ("failed", "planning_failed")


def test_repeated_resume_always_asks_for_a_fresh_run(project, monkeypatch):
    root = project / "work/migration_runs"
    first = saved_run(root, "first")
    second = saved_run(root, "second")
    choices = iter(["resume", str(first), "resume", str(second), "exit"])
    menus = []
    def select(title, options):
        menus.append(title)
        return next(choices)
    monkeypatch.setattr(interactive, "select_option", select)
    calls = []
    monkeypatch.setattr("cli.main.resume_pipeline", lambda root, run_id: calls.append(run_id) or root)
    assert main(["--run-id", "ignored"]) == 0
    assert calls == ["first", "second"]
    assert menus == ["What would you like to do?", "Select a run", "What would you like to do?", "Select a run", "What would you like to do?"]


def test_cancelled_resume_does_not_execute(project, monkeypatch):
    saved_run(project / "work/migration_runs")
    def select(title, options):
        if title == "Select a run":
            raise interactive.SelectionCancelled
        return "resume"
    monkeypatch.setattr(interactive, "select_option", select)
    monkeypatch.setattr("cli.main.resume_pipeline", lambda *_: pytest.fail("Resumed after cancellation"))
    assert main([]) == 130


def test_no_resumable_runs_reports_error_and_returns_menu(project, monkeypatch, capsys):
    saved_run(project / "work/migration_runs", phase="paused_awaiting_operator")
    choices = iter(["resume", "exit"])
    monkeypatch.setattr(interactive, "select_option", lambda *_: next(choices))
    monkeypatch.setattr("cli.main.resume_pipeline", lambda *_: pytest.fail("Resumed unsupported run"))
    assert main([]) == 0
    assert "No resumable runs with saved profiles" in capsys.readouterr().out


@pytest.mark.parametrize("failure", [False, True])
def test_explicit_resume_keeps_script_exit_behavior(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)
    monkeypatch.setattr(interactive, "select_option", lambda *_: pytest.fail("Unexpected menu"))
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    calls = []
    def resume(root, run_id):
        calls.append((root, run_id))
        if failure:
            raise RuntimeError("Failure")
        return tmp_path / run_id
    monkeypatch.setattr("cli.main.resume_pipeline", resume)
    assert main(["resume", "--config", "original.yaml", "--run-id", "explicit"]) == (1 if failure else 0)
    assert calls == [(str(tmp_path), "explicit")]
