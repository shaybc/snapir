"""Verify existing map selection, path validation, and intake without remapping."""

from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from cli.composer_map_configuration import collect_composer_map_configuration
from models.pipeline_configuration import PipelineConfiguration
from runtime.configuration import load_configuration


def existing_map(root):
    (root / "analysis").mkdir(parents=True)
    (root / "analysis/channel-operation-registry.md").write_text("WEB\n")
    return root


@pytest.mark.parametrize("absolute", [False, True])
def test_reuse_resolves_map_without_mapper_jar(tmp_path, absolute):
    vault = existing_map(tmp_path / "mapped")
    (tmp_path / "source").mkdir()
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(yaml.safe_dump(dict(source_root="source", channels=["WEB"],
        mapper_jar="missing.jar", existing_composer_map=str(vault) if absolute else "mapped")))
    profile = load_configuration(profile_path)
    assert profile.existing_composer_map == str(vault.resolve())
    assert PipelineConfiguration.model_validate_json(profile.model_dump_json()).existing_composer_map == str(vault.resolve())


@pytest.mark.parametrize("kind", ["missing", "file", "empty", "channel"])
def test_reuse_rejects_invalid_maps(tmp_path, kind):
    vault = tmp_path / "mapped"
    if kind == "file":
        vault.touch()
    elif kind == "empty":
        vault.mkdir()
    elif kind == "channel":
        existing_map(vault)
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(yaml.safe_dump(dict(source_root=".", channels=["OTHER"], existing_composer_map="mapped")))
    with pytest.raises(ValueError, match="existing map directory|missing required paths|missing selected channels"):
        load_configuration(profile_path)


def test_default_generation_still_requires_mapper_jar(tmp_path):
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(yaml.safe_dump(dict(source_root=".", mapper_jar="missing.jar")))
    with pytest.raises(ValueError, match="mapper_jar"):
        load_configuration(profile_path)


def test_map_selection_defaults_to_generation():
    def choose(title, options):
        assert options[0] == ("create", "Create a new map")
        return options[0][0]
    assert collect_composer_map_configuration(None, lambda *_: pytest.fail("Unexpected folder prompt"), choose) == {}


def test_existing_map_selection_retries_invalid_path(tmp_path):
    existing_map(tmp_path / "mapped")
    answers = iter(["", "missing", "mapped"])
    result = collect_composer_map_configuration(tmp_path, lambda *_: next(answers), lambda *_: "existing")
    assert result == dict(existing_composer_map="mapped")


def test_map_selection_cancellation_propagates(tmp_path):
    from cli.interactive import SelectionCancelled
    def cancel(*args):
        raise SelectionCancelled
    with pytest.raises(SelectionCancelled):
        collect_composer_map_configuration(tmp_path, cancel, lambda *_: "existing")


@pytest.mark.parametrize("reuse", [False, True])
def test_pipeline_map_choice_and_persisted_location(tmp_path, monkeypatch, reuse):
    from runtime import pipeline_runner as runner
    from tools.state_store_tools.db import get_connection
    from tools.state_store_tools.runs import get_run
    vault = existing_map(tmp_path / "mapped")
    before = {p.relative_to(vault): p.read_bytes() for p in vault.rglob("*") if p.is_file()}
    dummy = SimpleNamespace(issues=[], classes={}, model_dump_json=lambda **_: "{}")
    inventory = SimpleNamespace(java_dependencies=dummy, model_dump_json=lambda **_: "{}")
    monkeypatch.setattr(runner, "java_scope", lambda _: nullcontext())
    monkeypatch.setattr(runner, "discover_java_sources", lambda *_: dummy)
    monkeypatch.setattr(runner, "discover_java_classpath", lambda *_: dummy)
    monkeypatch.setattr("tools.component_inventory_tools.build_component_inventory", lambda *_: inventory)
    monkeypatch.setattr("tools.state_store_tools.component_inventory.persist_component_inventory", lambda *_: None)
    monkeypatch.setattr("tools.state_store_tools.component_inventory.get_implementation_usage", lambda *_: [])
    monkeypatch.setattr("tools.state_store_tools.component_inventory.get_configured_component_usage", lambda *_: [])
    commands, imported = [], []
    monkeypatch.setattr(runner, "run_java", lambda command, **kwargs:
                        commands.append(command) or SimpleNamespace(stdout="mapper output", stderr="", returncode=0))
    monkeypatch.setattr(runner, "run_legacy_composer_analysis", lambda conn, config:
                        imported.append(config.vault_root) or {"paused": True})
    profile = PipelineConfiguration(source_root=str(tmp_path), output_root=str(tmp_path / "runs"),
        channels=["WEB"], model_provider="mock", mapper_jar="missing.jar",
        existing_composer_map=str(vault) if reuse else None)
    directory = runner.run_pipeline(profile, "reuse-test")
    expected = str(vault if reuse else directory / "vault")
    assert imported == [expected]
    assert len(commands) == (0 if reuse else 1)
    assert (directory / "logs/mapper.log").exists() is (not reuse)
    if reuse:
        assert not (directory / "vault").exists()
    assert {p.relative_to(vault): p.read_bytes() for p in vault.rglob("*") if p.is_file()} == before
    assert json.loads((directory / "state/profile.json").read_text())["existing_composer_map"] == profile.existing_composer_map
    conn = get_connection(str(directory / "state/migration.db"))
    try:
        assert get_run(conn, "reuse-test")["run_config_json"]["vault_root"] == expected
    finally:
        conn.close()
