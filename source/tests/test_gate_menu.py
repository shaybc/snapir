"""Verify interactive gate decisions using isolated test databases only."""

from runtime.workspace_paths import run_report_path, write_run_report
import hashlib
import sqlite3
from types import SimpleNamespace

import pytest

from cli import interactive
from cli.main import main


def saved_run(root, run_id="existing", phase="gate_2_pending", *, report=True):
    directory = root / run_id
    state = directory / "state"
    state.mkdir(parents=True)
    with sqlite3.connect(state / "migration.db") as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT, status TEXT, current_phase TEXT)")
        conn.execute("INSERT INTO runs VALUES (?, 'paused', ?)", (run_id, phase))
    if report:
        for gate in range(1, 5):
            write_run_report(directory, f"gate_{gate}_report.txt", f"Gate {gate} evidence")
    return directory


def decisions(directory):
    with sqlite3.connect(directory / "state/migration.db") as conn:
        exists = conn.execute("SELECT name FROM sqlite_master WHERE name='runtime_gate_decisions'").fetchone()
        return conn.execute("SELECT gate_number, report_hash, decision, policy FROM runtime_gate_decisions").fetchall() if exists else []


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(interactive, "project_root", lambda: tmp_path)
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)
    monkeypatch.setattr("cli.status_discovery.constants.OUTPUT_ROOT", "work/migration_runs")
    monkeypatch.setattr("cli.main.load_configuration", lambda *_: pytest.fail("Loaded original config"))
    monkeypatch.setattr("cli.main.run_pipeline", lambda *_: pytest.fail("Started migration"))
    monkeypatch.setattr("cli.main.resume_pipeline", lambda *_: pytest.fail("Automatically resumed"))
    return tmp_path


@pytest.mark.parametrize("command, decision", [("approve", "approved"), ("reject", "rejected")])
@pytest.mark.parametrize("phase", ["gate_2_pending", "gate_2_rejected"])
def test_gate_inferred_recorded_and_result_visible_before_menu(project, monkeypatch, capsys, command, decision, phase):
    directory = saved_run(project / "work/migration_runs", phase=phase)
    choices = iter([command, str(directory), "exit"])
    events = []
    def select(title, options):
        assert title != "Select a configuration"
        selected = next(choices)
        if selected == "exit":
            output = capsys.readouterr().out
            assert f"Gate 2 {decision} for run: existing" in output
            assert "Decision recorded. Resume the run to continue." in output
            assert events == []
        return selected
    monkeypatch.setattr(interactive, "select_option", select)
    monkeypatch.setattr("cli.main.clear_screen", lambda: events.append("clear"))
    assert main([]) == 0
    digest = hashlib.sha256(b"Gate 2 evidence").hexdigest()
    assert decisions(directory) == [(2, digest, decision, "human")]


@pytest.mark.parametrize("command", ["approve", "reject"])
def test_no_waiting_gate_reports_message_and_returns_without_mutation(project, monkeypatch, capsys, command):
    directory = saved_run(project / "work/migration_runs", phase="planning_inputs_ready")
    database = directory / "state/migration.db"
    before = database.read_bytes()
    choices = iter([command, "exit"])
    monkeypatch.setattr(interactive, "select_option", lambda *_: next(choices))
    assert main([]) == 0
    assert "No gate awaiting a decision" in capsys.readouterr().out
    assert database.read_bytes() == before
    assert decisions(directory) == []


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("failure", ["report", "database"])
def test_gate_errors_return_to_menu_with_optional_trace(project, monkeypatch, capsys, verbose, failure):
    directory = saved_run(project / "work/migration_runs", report=failure != "report")
    choices = iter(["approve", str(directory), "exit"])
    def select(title, options):
        selected = next(choices)
        if selected == str(directory) and failure == "database":
            (directory / "state/migration.db").write_text("corrupt")
        if selected == "exit":
            output = capsys.readouterr()
            assert "Migration error:" in output.out
            assert "Decision recorded" not in output.out
            assert ("Traceback" in output.err) == verbose
        return selected
    monkeypatch.setattr(interactive, "select_option", select)
    assert main(["--verbose"] if verbose else []) == 0
    if failure == "report":
        assert decisions(directory) == []


def test_subsequent_gate_action_uses_fresh_run_and_gate(project, monkeypatch):
    root = project / "work/migration_runs"
    first = saved_run(root, "first", "gate_1_pending")
    second = saved_run(root, "second", "gate_3_pending")
    choices = iter(["approve", str(first), "reject", str(second), "exit"])
    monkeypatch.setattr(interactive, "select_option", lambda *_: next(choices))
    assert main(["--config", "retained.yaml", "--run-id", "ignored", "--gate", "1"]) == 0
    assert decisions(first)[0][0:3:2] == (1, "approved")
    assert decisions(second)[0][0:3:2] == (3, "rejected")


def test_changed_checkpoint_is_rechecked_before_recording(project, monkeypatch, capsys):
    directory = saved_run(project / "work/migration_runs")
    choices = iter(["approve", str(directory), "exit"])
    def select(title, options):
        selected = next(choices)
        if selected == str(directory):
            with sqlite3.connect(directory / "state/migration.db") as conn:
                conn.execute("UPDATE runs SET current_phase='planning_inputs_ready'")
        return selected
    monkeypatch.setattr(interactive, "select_option", select)
    assert main([]) == 0
    assert "No gate awaiting a decision for this run" in capsys.readouterr().out
    assert decisions(directory) == []


def test_cancelled_gate_selection_preserves_decisions(project, monkeypatch):
    directory = saved_run(project / "work/migration_runs")
    def select(title, options):
        if title == "Select a run awaiting a gate decision":
            raise interactive.SelectionCancelled
        return "approve"
    monkeypatch.setattr(interactive, "select_option", select)
    assert main([]) == 130
    assert decisions(directory) == []


@pytest.mark.parametrize("command", ["approve", "reject"])
def test_explicit_gate_scripts_preserve_success_exit(tmp_path, monkeypatch, command):
    directory = saved_run(tmp_path)
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)
    monkeypatch.setattr(interactive, "select_option", lambda *_: pytest.fail("Unexpected menu"))
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    assert main([command, "--config", "original.yaml", "--run-id", "existing", "--gate", "2"]) == 0
    assert decisions(directory)[0][2] == ("approved" if command == "approve" else "rejected")


@pytest.mark.parametrize("command", ["approve", "reject"])
def test_explicit_gate_missing_flag_still_errors(tmp_path, monkeypatch, command):
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    with pytest.raises(SystemExit) as error:
        main([command, "--config", "original.yaml", "--run-id", "existing"])
    assert error.value.code == 2


@pytest.mark.parametrize("command", ["approve", "reject"])
def test_explicit_gate_operational_failure_still_exits_one(tmp_path, monkeypatch, command):
    directory = saved_run(tmp_path, report=False)
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)
    monkeypatch.setattr(interactive, "select_option", lambda *_: pytest.fail("Unexpected menu"))
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    assert main([command, "--config", "original.yaml", "--run-id", "existing", "--gate", "2"]) == 1
    assert decisions(directory) == []
