"""Verify interactive CLI completion without running migrations."""

import sqlite3
from types import SimpleNamespace
from pathlib import Path

import pytest

from cli import interactive
from cli.discovery import discover_configurations, discover_runs
from cli.main import main
from runtime.configuration import load_configuration


def make_run(root, run_id="existing", phase="planning_inputs_ready"):
    state = root / run_id / "state"
    state.mkdir(parents=True)
    (state / "profile.json").write_text("{}")
    with sqlite3.connect(state / "migration.db") as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT, status TEXT, current_phase TEXT)")
        conn.execute("INSERT INTO runs VALUES (?, 'paused', ?)", (run_id, phase))
    return state.parent


@pytest.fixture
def terminal(monkeypatch):
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)


@pytest.mark.parametrize("arguments", [[], ["start"], ["--config", "config.yaml"]])
def test_missing_arguments_without_terminal_fail(arguments, monkeypatch):
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)
    monkeypatch.setattr(interactive, "select_option", lambda *_: pytest.fail("Unexpected prompt"))
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


def test_help_does_not_prompt(monkeypatch):
    monkeypatch.setattr(interactive, "select_option", lambda *_: pytest.fail("Unexpected prompt"))
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0


@pytest.mark.parametrize("command", ["start", "resume"])
def test_command_menu_dispatches_selection(tmp_path, monkeypatch, terminal, command):
    make_run(tmp_path)
    choices = iter([command, "configs/bank_demo.yaml", "existing"])
    def select(title, options):
        if title == "What would you like to do?":
            assert [value for value, _ in options] == ["create_config", "start", "resume", "status", "approve", "reject", "documentation", "exit"]
        return next(choices)
    monkeypatch.setattr(interactive, "select_option", select)
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    calls = []
    monkeypatch.setattr("cli.main.run_pipeline", lambda profile, run_id: calls.append(("start", run_id)) or tmp_path)
    monkeypatch.setattr("cli.main.resume_pipeline", lambda root, run_id: calls.append(("resume", run_id)) or tmp_path)
    assert main([]) == 0
    assert calls[0][0] == command
    assert calls[0][1] == "existing" if command == "resume" else calls[0][1].startswith("run-")


@pytest.mark.parametrize("command", ["start", "resume"])
def test_explicit_command_preserved(tmp_path, monkeypatch, terminal, command):
    make_run(tmp_path)
    selections = iter(["configs/bank_demo.yaml", "existing"])
    monkeypatch.setattr(interactive, "select_option", lambda *_: next(selections))
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    calls = []
    monkeypatch.setattr("cli.main.run_pipeline", lambda *args: calls.append("start") or tmp_path)
    monkeypatch.setattr("cli.main.resume_pipeline", lambda *args: calls.append("resume") or tmp_path)
    assert main([command]) == 0
    assert calls == [command]


def test_explicit_start_never_prompts(tmp_path, monkeypatch, terminal):
    monkeypatch.setattr(interactive, "select_option", lambda *_: pytest.fail("Unexpected prompt"))
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    monkeypatch.setattr("cli.main.run_pipeline", lambda profile, run_id: tmp_path if run_id == "supplied" else pytest.fail())
    assert main(["start", "--config", "supplied.yaml", "--run-id", "supplied"]) == 0


def test_cancellation_precedes_configuration_and_mutation(monkeypatch, terminal):
    def cancel(*args):
        raise interactive.SelectionCancelled
    monkeypatch.setattr(interactive, "select_option", cancel)
    monkeypatch.setattr("cli.main.load_configuration", lambda _: pytest.fail("Loaded after cancellation"))
    assert main([]) == 130


def test_discovery_ignores_legacy_and_invalid_databases(tmp_path):
    make_run(tmp_path)
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "migration.db").write_text("")
    corrupt = make_run(tmp_path, "corrupt")
    (corrupt / "state" / "migration.db").write_text("invalid")
    runs = discover_runs(str(tmp_path))
    assert len(runs) == 1
    assert runs[0][0] == "existing"
    assert "planning_inputs_ready" in runs[0][1]
    assert not (legacy / "state").exists()


def test_config_discovery_and_relative_output_root(tmp_path, monkeypatch, terminal):
    configs = tmp_path / "configs"
    configs.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    mapper = tmp_path / "mapper.jar"
    mapper.touch()
    text = Path("configs/bank_demo.yaml").read_text(encoding="utf-8")
    import yaml
    data = yaml.safe_load(text)
    data.update(source_root="../source", mapper_jar="../mapper.jar", output_root="../selected-runs")
    config = configs / "project.yml"
    config.write_text(yaml.safe_dump(data))
    ignored = tmp_path / "generated"
    ignored.mkdir()
    (ignored / "ignored.yaml").touch()
    assert discover_configurations(tmp_path) == [config]
    root = tmp_path / "selected-runs"
    make_run(root)
    profile = load_configuration(config)
    args = SimpleNamespace(command="resume", run_id=None)
    monkeypatch.setattr(interactive, "select_option", lambda title, options: options[0][0])
    interactive.complete_run_selection(args, profile)
    assert args.run_id == "existing"


@pytest.mark.parametrize("command", ["status", "approve", "reject"])
def test_inspection_and_gate_menus_only_offer_existing(tmp_path, monkeypatch, terminal, command):
    make_run(tmp_path)
    def select(title, options):
        assert [value for value, _ in options] == ["existing"]
        return "existing"
    monkeypatch.setattr(interactive, "select_option", select)
    args = SimpleNamespace(command=command, run_id=None)
    interactive.complete_run_selection(args, SimpleNamespace(output_root=str(tmp_path)))
    assert args.command == command
    assert args.run_id == "existing"


def test_actual_arrow_navigation_and_escape(monkeypatch):
    from prompt_toolkit.application import Application
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    with create_pipe_input() as pipe:
        monkeypatch.setattr("prompt_toolkit.application.Application", lambda **kwargs:
                            Application(**kwargs, input=pipe, output=DummyOutput()))
        pipe.send_text("\x1b[B\r")
        assert interactive.select_option("Choose", [("first", "First"), ("second", "Second")]) == "second"
        pipe.send_text("\x1b[A\r")
        assert interactive.select_option("Choose", [("first", "First"), ("second", "Second")]) == "second"
        pipe.send_text("\x1b")
        with pytest.raises(interactive.SelectionCancelled):
            interactive.select_option("Choose", [("first", "First")])
        pipe.send_text("\x03")
        with pytest.raises(interactive.SelectionCancelled):
            interactive.select_option("Choose", [("first", "First")])


def test_no_runs_and_resumable_filter(tmp_path, monkeypatch, terminal):
    assert discover_runs(str(tmp_path / "absent")) == []
    make_run(tmp_path, phase="unsupported")
    assert discover_runs(str(tmp_path), resumable_only=True) == []
    args = SimpleNamespace(command="resume", run_id=None)
    with pytest.raises(ValueError, match="No current-layout runs"):
        interactive.complete_run_selection(args, SimpleNamespace(output_root=str(tmp_path)))


def test_no_configurations(monkeypatch, terminal):
    monkeypatch.setattr(interactive, "discover_configurations", lambda _: [])
    args = SimpleNamespace(command="start", config=None)
    with pytest.raises(ValueError, match="No YAML configurations"):
        interactive.complete_arguments(args, None)


def test_explicit_resume_does_not_prompt(tmp_path, monkeypatch, terminal):
    monkeypatch.setattr(interactive, "select_option", lambda *_: pytest.fail("Unexpected prompt"))
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    calls = []
    monkeypatch.setattr("cli.main.resume_pipeline", lambda root, run_id: calls.append((root, run_id)) or tmp_path)
    assert main(["resume", "--config", "supplied.yaml", "--run-id", "supplied"]) == 0
    assert calls == [(str(tmp_path), "supplied")]


def test_gate_still_required(monkeypatch, terminal):
    monkeypatch.setattr(interactive, "select_option", lambda *_: pytest.fail("Unexpected prompt"))
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root="unused"))
    with pytest.raises(SystemExit) as error:
        main(["approve", "--config", "supplied.yaml"])
    assert error.value.code == 2


@pytest.mark.parametrize("cancel_at", [2, 3])
def test_later_cancellation_never_executes(tmp_path, monkeypatch, terminal, cancel_at):
    make_run(tmp_path)
    count = 0
    def select(*args):
        nonlocal count
        count += 1
        if count == cancel_at:
            raise interactive.SelectionCancelled
        return "resume" if count == 1 else "configs/bank_demo.yaml"
    monkeypatch.setattr(interactive, "select_option", select)
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root=str(tmp_path)))
    monkeypatch.setattr("cli.main.run_pipeline", lambda *args: pytest.fail("Executed after cancellation"))
    monkeypatch.setattr("cli.main.resume_pipeline", lambda *args: pytest.fail("Executed after cancellation"))
    assert main([]) == 130


def test_supplied_configuration_is_preserved(tmp_path, monkeypatch, terminal):
    monkeypatch.setattr(interactive, "select_option", lambda *_: "start")
    loaded = []
    monkeypatch.setattr("cli.main.load_configuration", lambda path:
                        loaded.append(path) or SimpleNamespace(output_root=str(tmp_path)))
    monkeypatch.setattr("cli.main.run_pipeline", lambda *args: tmp_path)
    assert main(["--config", "supplied.yaml"]) == 0
    assert loaded == ["supplied.yaml"]
