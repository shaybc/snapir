"""Verify Composer config collection and saving without running migrations."""

from pathlib import Path

import pytest
import yaml

from cli import configuration_wizard as wizard
from cli import interactive, multiselect
from cli.configuration_discovery import discover_channel_directories, discover_operations
from cli.main import main
from runtime.configuration import load_configuration


def operation_file(root, project, channel, name, filename="definition.xml"):
    folder = root / project / "src" / "Xml Definition" / "Channel" / channel / "selfDefOper"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_text(f'<XML><CCDSEServerOperation id="{name}"/></XML>')
    return folder


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(wizard, "__file__", str(tmp_path / "cli" / "configuration_wizard.py"))
    source = tmp_path / "bank-demo" / "composer" / "Workspace"
    operation_file(source, "first", "WEB", "WebOperation")
    operation_file(source, "second", "VOICE", "VoiceOperation")
    jar = tmp_path / "composer-mapper" / "target" / "composer-mapper-1.1.1-jar-with-dependencies.jar"
    jar.parent.mkdir(parents=True)
    jar.touch()
    return tmp_path


def collect_defaults(monkeypatch, name="new_config", *, cancel_at=None):
    prompts = []
    def text(title, default=""):
        prompts.append((title, default))
        return default or name
    monkeypatch.setattr(wizard, "prompt_text", text)
    def multiple(title, options, **kwargs):
        assert kwargs == {"select_all": True}
        if title == cancel_at:
            raise interactive.SelectionCancelled
        if title == "Select channels":
            assert [value for value, _ in options] == ["VOICE", "WEB"]
            return ["WEB"]
        if title == "Select operations":
            assert options == [("WebOperation", "WebOperation")]
            assert kwargs == {"select_all": True}
            return ["WebOperation"]
        assert options == [("java", "Java")]
        return ["java"]
    monkeypatch.setattr(wizard, "select_multiple", multiple)
    return prompts


def test_bank_demo_discovers_actual_channels_and_operation_ids():
    source = Path("bank-demo/composer/Workspace")
    channels = discover_channel_directories(source)
    assert list(channels) == ["INTERNET", "IVR", "XML"]
    internet = discover_operations(channels, ["INTERNET"])
    assert internet == ["GetAccountDetailsOp", "GetClientAccountsOp", "GetClientLinksOp", "TransferFundsOp"]
    ivr = discover_operations(channels, ["IVR"])
    assert "GetAccountBalanceOp" in ivr
    assert "TransferFundsOp" not in ivr
    assert discover_operations(channels, ["XML"]) == []


def test_custom_workspace_filters_channels_and_deduplicates_ids(tmp_path):
    folder = operation_file(tmp_path, "any-project", "CUSTOM", "ActualId", "unrelated-filename.xml")
    operation_file(tmp_path, "another", "OTHER", "OtherId")
    (folder / "duplicate.xml").write_text('<XML><CCDSEServerOperation id="ActualId"/></XML>')
    (folder / "not-an-operation.xml").write_text('<XML><opStep id="NotAnOperation"/></XML>')
    channels = discover_channel_directories(tmp_path)
    assert list(channels) == ["CUSTOM", "OTHER"]
    assert discover_operations(channels, ["CUSTOM"]) == ["ActualId"]


def test_defaults_and_yaml_round_trip(project, monkeypatch):
    prompts = collect_defaults(monkeypatch)
    destination = wizard.create_configuration()
    assert destination == project / "configs" / "new_config.yaml"
    data = yaml.safe_load(destination.read_text())
    assert data == {
        "source_root": "../bank-demo/composer/Workspace",
        "mapper_jar": "../composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar",
        "output_root": "../work/migration_runs", "channels": ["WEB"],
        "include_operations": ["WebOperation"], "target_languages": ["java"],
    }
    loaded = load_configuration(destination)
    assert loaded.source_root == str((project / "bank-demo/composer/Workspace").resolve())
    assert loaded.output_root == str((project / "work/migration_runs").resolve())
    assert len(prompts) == 4
    assert list(destination.parent.iterdir()) == [destination]


def test_custom_paths_are_preserved_and_config_relative(project, monkeypatch):
    collect_defaults(monkeypatch)
    values = iter(["custom", "../bank-demo/composer/Workspace", "../composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar", "../other-output"])
    monkeypatch.setattr(wizard, "prompt_text", lambda *_: next(values))
    destination = wizard.create_configuration()
    assert load_configuration(destination).output_root == str((project / "other-output").resolve())
    assert yaml.safe_load(destination.read_text())["output_root"] == "../other-output"


def test_absolute_input_paths_are_preserved(project, monkeypatch):
    collect_defaults(monkeypatch)
    source = str(project / "bank-demo/composer/Workspace")
    jar = str(project / "composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar")
    output = str(project / "absolute-output")
    values = iter(["absolute", source, jar, output])
    monkeypatch.setattr(wizard, "prompt_text", lambda *_: next(values))
    destination = wizard.create_configuration()
    data = yaml.safe_load(destination.read_text())
    assert (data["source_root"], data["mapper_jar"], data["output_root"]) == (source, jar, output)
    assert load_configuration(destination).output_root == str(Path(output).resolve())


@pytest.mark.parametrize("name", ["../bad", "a/b", "a\\b", "", "bad.yaml", "CON", "nul", "C:drive"])
def test_config_name_rejects_unsafe_or_reserved_names(tmp_path, name):
    with pytest.raises(ValueError):
        wizard.configuration_path(tmp_path, name)


def test_invalid_paths_reprompt(project, monkeypatch, capsys):
    values = iter(["../absent", "../bank-demo/composer/Workspace"])
    monkeypatch.setattr(wizard, "prompt_text", lambda *_: next(values))
    assert wizard.collect_path(project / "configs", "source_root", "default") == "../bank-demo/composer/Workspace"
    assert "must identify an existing directory" in capsys.readouterr().out
    values = iter(["../bank-demo", "../composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar"])
    assert wizard.collect_path(project / "configs", "mapper_jar", "default").endswith("dependencies.jar")


@pytest.mark.parametrize("cancel_at", ["Select channels", "Select operations", "Select target languages"])
def test_cancellation_creates_no_partial_config(project, monkeypatch, cancel_at):
    collect_defaults(monkeypatch, cancel_at=cancel_at)
    with pytest.raises(interactive.SelectionCancelled):
        wizard.create_configuration()
    assert not (project / "configs").exists()


@pytest.mark.parametrize("replace", [False, True])
def test_existing_config_requires_explicit_replacement(project, monkeypatch, replace):
    collect_defaults(monkeypatch)
    destination = project / "configs" / "new_config.yaml"
    destination.parent.mkdir()
    destination.write_text("existing content")
    def confirm(title, options):
        assert "already exists" in title
        assert options[0] == ("cancel", "Cancel")
        return "replace" if replace else "cancel"
    monkeypatch.setattr(wizard, "select_option", confirm)
    if replace:
        assert wizard.create_configuration() == destination
        assert load_configuration(destination).channels == ["WEB"]
    else:
        with pytest.raises(interactive.SelectionCancelled):
            wizard.create_configuration()
        assert destination.read_text() == "existing content"


def test_new_file_save_refuses_racing_existing_name(project):
    destination = project / "configs" / "race.yaml"
    destination.parent.mkdir()
    destination.write_text("preserve")
    data = {"source_root": "../bank-demo/composer/Workspace", "mapper_jar": "../composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar",
            "output_root": "../work/migration_runs", "channels": ["WEB"]}
    with pytest.raises(FileExistsError):
        wizard.save_configuration(destination, data, overwrite=False)
    assert destination.read_text() == "preserve"
    assert list(destination.parent.iterdir()) == [destination]


def test_empty_selection_does_not_save(project, monkeypatch):
    collect_defaults(monkeypatch)
    monkeypatch.setattr(wizard, "select_multiple", lambda *_args, **_kwargs: [])
    with pytest.raises(ValueError, match="Select at least one"):
        wizard.create_configuration()
    assert not (project / "configs").exists()


def test_unsupported_language_is_rejected_before_saving(project):
    destination = project / "configs" / "unsupported.yaml"
    data = {"source_root": "../bank-demo/composer/Workspace", "mapper_jar": "../composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar",
            "output_root": "../work/migration_runs", "channels": ["WEB"], "target_languages": ["python"]}
    with pytest.raises(ValueError):
        wizard.save_configuration(destination, data, overwrite=False)
    assert not destination.parent.exists()


def test_menu_create_returns_to_menu_then_exits_without_migration(monkeypatch):
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)
    selections = iter(["create_config", "exit"])
    menus = []
    def select(title, options):
        assert options[0] == ("create_config", "Create a new config")
        menus.append(title)
        return next(selections)
    monkeypatch.setattr(interactive, "select_option", select)
    calls = []
    monkeypatch.setattr("cli.main.create_configuration", lambda: calls.append("create"))
    for name in ("load_configuration", "complete_run_selection", "run_pipeline", "resume_pipeline"):
        monkeypatch.setattr(f"cli.main.{name}", lambda *_args: pytest.fail("Unexpected pipeline/config action"))
    assert main([]) == 0
    assert calls == ["create"]
    assert menus == ["What would you like to do?", "What would you like to do?"]


def test_created_config_is_discovered_on_subsequent_start(project, monkeypatch):
    collect_defaults(monkeypatch)
    monkeypatch.setattr(interactive, "__file__", str(project / "cli/interactive.py"))
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)
    selections = iter(["create_config", "start"])
    menus = []
    def select(title, options):
        menus.append(title)
        if title == "Select a configuration":
            assert options == [(str(project / "configs/new_config.yaml"), "configs\\new_config.yaml")]
            return options[0][0]
        return next(selections)
    monkeypatch.setattr(interactive, "select_option", select)
    calls = []
    monkeypatch.setattr("cli.main.run_pipeline", lambda profile, run_id:
                        calls.append((profile, run_id)) or project)
    assert main([]) == 0
    assert menus == ["What would you like to do?", "What would you like to do?", "Select a configuration"]
    assert len(calls) == 1
    assert calls[0][0].channels == ["WEB"]


def test_return_to_menu_preserves_supplied_arguments(project, monkeypatch):
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)
    selections = iter(["create_config", "start"])
    monkeypatch.setattr(interactive, "select_option", lambda title, options: next(selections))
    monkeypatch.setattr("cli.main.create_configuration", lambda: None)
    loaded = []
    monkeypatch.setattr("cli.main.load_configuration", lambda path: loaded.append(path) or "profile")
    calls = []
    monkeypatch.setattr("cli.main.run_pipeline", lambda profile, run_id:
                        calls.append((profile, run_id)) or project)
    assert main(["--config", "supplied.yaml", "--run-id", "supplied", "--verbose"]) == 0
    assert loaded == ["supplied.yaml"]
    assert calls == [("profile", "supplied")]


@pytest.mark.parametrize("keys, expected", [
    ("\x1b[B \x1b[A\r", ["one", "two"]),
    ("\x1b[B\x1b[B \x1b[A\x1b[A\r", ["one"]),
    ("\x1b[B  \x1b[B \x1b[A\x1b[A\r", ["one"]),
])
def test_multiselect_space_select_all_and_done(monkeypatch, keys, expected):
    from prompt_toolkit.application import Application
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    with create_pipe_input() as pipe:
        def application(**kwargs):
            fragments = kwargs["layout"].container.content.text()
            assert [text.strip() for _, text in fragments[:3]] == ["Done", "[ ] Select all", "────────────────────────"]
            return Application(**kwargs, input=pipe, output=DummyOutput())
        monkeypatch.setattr("prompt_toolkit.application.Application", application)
        pipe.send_text(keys)
        assert multiselect.select_multiple("Choose", [("one", "One"), ("two", "Two")], select_all=True) == expected


def test_empty_done_stays_open_until_selection_and_cancellation(monkeypatch):
    from prompt_toolkit.application import Application
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    with create_pipe_input() as pipe:
        monkeypatch.setattr("prompt_toolkit.application.Application", lambda **kwargs:
                            Application(**kwargs, input=pipe, output=DummyOutput()))
        pipe.send_text("\r\x1b[B\x1b[B \x1b[A\x1b[A\r")
        assert multiselect.select_multiple("Choose", [("java", "Java")], select_all=True) == ["java"]
        pipe.send_text("\x03")
        with pytest.raises(interactive.SelectionCancelled):
            multiselect.select_multiple("Choose", [("java", "Java")], select_all=True)


def test_text_prompt_enter_accepts_displayed_default(monkeypatch):
    from prompt_toolkit import PromptSession
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    with create_pipe_input() as pipe:
        session = PromptSession(input=pipe, output=DummyOutput())
        monkeypatch.setattr("prompt_toolkit.prompt", session.prompt)
        pipe.send_text("\r")
        assert wizard.prompt_text("source_root", "../default") == "../default"
        pipe.send_text("../custom\r")
        assert wizard.prompt_text("source_root", "../default") == "../custom"
        pipe.send_text("\x1b")
        with pytest.raises(interactive.SelectionCancelled):
            wizard.prompt_text("source_root", "../default")
