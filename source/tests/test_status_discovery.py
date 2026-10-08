"""Verify configuration-independent Status discovery without migration mutations."""

import sqlite3
from types import SimpleNamespace

import pytest
import yaml

from cli import interactive
from cli.main import main
from cli.status_discovery import discover_run_roots, discover_status_runs


def saved_run(root, run_id, phase="planning_inputs_ready"):
    directory = root / run_id
    state = directory / "state"
    state.mkdir(parents=True)
    with sqlite3.connect(state / "migration.db") as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT, status TEXT, current_phase TEXT)")
        conn.execute("INSERT INTO runs VALUES (?, 'paused', ?)", (run_id, phase))
    return directory


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(interactive, "project_root", lambda: tmp_path)
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)
    monkeypatch.setattr("cli.status_discovery.constants.OUTPUT_ROOT", "work/migration_runs")
    return tmp_path


def test_default_root_status_without_configs_or_source_inputs(project, monkeypatch, capsys):
    directory = saved_run(project / "work/migration_runs", "persisted")
    choices = iter(["status", str(directory), "exit"])
    def select(title, options):
        assert title != "Select a configuration"
        return next(choices)
    monkeypatch.setattr(interactive, "select_option", select)
    monkeypatch.setattr("cli.main.load_configuration", lambda *_: pytest.fail("Loaded a config"))
    monkeypatch.setattr("cli.main.complete_run_selection", lambda *_: pytest.fail("Used config-based run selection"))
    assert main([]) == 0
    assert '"run_id": "persisted"' in capsys.readouterr().out
    assert not (project / "configs").exists()
    assert not (directory / "state/profile.json").exists()


def test_alternate_shared_roots_and_duplicate_ids(project):
    configs = project / "configs"
    configs.mkdir()
    alternate = project / "other-runs"
    first = saved_run(project / "work/migration_runs", "same", phase="default_checkpoint")
    second = saved_run(alternate, "same", phase="alternate_checkpoint")
    saved_run(alternate, "another")
    for name in ("one", "two"):
        (configs / f"{name}.yaml").write_text(yaml.safe_dump({
            "output_root": "../other-runs", "source_root": "../missing", "mapper_jar": "../missing.jar",
        }))
    (configs / "default.yaml").write_text("output_root: ../work/migration_runs\n")
    (configs / "broken.yaml").write_text("bad: [\n")
    (configs / "invalid-path.yaml").write_text("output_root: 42\n")
    (configs / "not-a-mapping.yml").write_text("- invalid\n")
    ignored = project / "generated"
    ignored.mkdir()
    (ignored / "ignored.yaml").write_text("output_root: ../ignored-runs\n")
    assert discover_run_roots(project) == sorted([alternate, project / "work/migration_runs"])
    choices = discover_status_runs(project)
    assert len(choices) == 3
    labels = dict(choices)
    assert "default_checkpoint" in labels[str(first)]
    assert "alternate_checkpoint" in labels[str(second)]
    assert "work" in labels[str(first)] and "other-runs" in labels[str(second)]


def test_selected_directory_is_authoritative_across_duplicate_ids(project, monkeypatch, capsys):
    configs = project / "configs"
    configs.mkdir()
    (configs / "alternate.yaml").write_text("output_root: ../alternate\n")
    saved_run(project / "work/migration_runs", "same", phase="not-selected")
    selected = saved_run(project / "alternate", "same", phase="selected-checkpoint")
    choices = iter(["status", str(selected), "exit"])
    monkeypatch.setattr(interactive, "select_option", lambda *_: next(choices))
    monkeypatch.setattr("cli.main.load_configuration", lambda *_: pytest.fail("Loaded retained config"))
    assert main(["--config", "unusable-config.yaml", "--run-id", "ignored"]) == 0
    output = capsys.readouterr().out
    assert "selected-checkpoint" in output and "not-selected" not in output


def test_invalid_or_legacy_runs_are_skipped_without_creating_databases(project):
    root = project / "work/migration_runs"
    saved_run(root, "valid")
    legacy = root / "legacy"
    legacy.mkdir()
    (legacy / "migration.db").write_text("")
    invalid_name = saved_run(root, "has spaces")
    corrupt = saved_run(root, "corrupt")
    (corrupt / "state/migration.db").write_text("corrupt")
    assert [path for path, _ in discover_status_runs(project)] == [str(root / "valid")]
    assert not (legacy / "state").exists()
    assert invalid_name.is_dir()


def test_status_retains_config_for_next_start(project, monkeypatch):
    directory = saved_run(project / "work/migration_runs", "existing")
    choices = iter(["status", str(directory), "start", "exit"])
    monkeypatch.setattr(interactive, "select_option", lambda *_: next(choices))
    loaded = []
    monkeypatch.setattr("cli.main.load_configuration", lambda path:
                        loaded.append(path) or SimpleNamespace(output_root=str(project)))
    monkeypatch.setattr("cli.main.run_pipeline", lambda *_: project / "new-run")
    assert main(["--config", "retained.yaml", "--run-id", "ignored"]) == 0
    assert loaded == ["retained.yaml"]
