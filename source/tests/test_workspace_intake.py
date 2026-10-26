from __future__ import annotations

from pathlib import Path

from tools.workspace_intake_tools.channel_validator import validate_channel_in_registry
from tools.workspace_intake_tools.env_loader import load_env_with_fallbacks
from tools.workspace_intake_tools.run_factory import create_run_config
from workspace_intake import validate_startup
from workspace_intake import run_composer_mapper
from types import SimpleNamespace
import pytest


def write_env(path: Path, content: str) -> Path:
    path.write_text(content.strip() + "\n")
    return path


def make_valid_workspace(tmp_path: Path) -> dict:
    composer_root = tmp_path / "composer"
    composer_root.mkdir()
    (composer_root / "operation.xml").write_text("<operation/>")
    vault_root = tmp_path / "vault"
    analysis = vault_root / "analysis"
    analysis.mkdir(parents=True)
    (analysis / "channel-operation-registry.md").write_text("| INTERNET | GetClientLinks.xml |\n")
    return {
        "COMPOSER_ROOT": str(composer_root),
        "VAULT_ROOT": str(vault_root),
        "OUTPUT_ROOT": str(tmp_path / "out"),
        "DB_PATH": str(tmp_path / "state.db"),
    }


def test_missing_composer_root_fails_with_clear_error(tmp_path):
    env = load_env_with_fallbacks()
    env.update(make_valid_workspace(tmp_path))
    env["COMPOSER_ROOT"] = str(tmp_path / "missing")

    errors = validate_startup(env)

    assert any("COMPOSER_ROOT does not exist" in error for error in errors)


def test_multi_channel_with_no_target_channels_fails(tmp_path):
    env = load_env_with_fallbacks()
    env.update(make_valid_workspace(tmp_path))
    env["RUN_MODE"] = "multi_channel"
    env["TARGET_CHANNELS"] = []

    errors = validate_startup(env)

    assert "multi_channel requires one or more TARGET_CHANNELS values" in errors


def test_unknown_target_language_fails(tmp_path):
    env = load_env_with_fallbacks()
    env.update(make_valid_workspace(tmp_path))
    env["TARGET_LANGUAGES"] = ["ruby"]

    errors = validate_startup(env)

    assert "TARGET_LANGUAGE is not supported: ruby" in errors


def test_target_channel_not_in_registry_fails(tmp_path):
    workspace = make_valid_workspace(tmp_path)

    missing = validate_channel_in_registry(workspace["VAULT_ROOT"], ["IVR"])

    assert missing == ["IVR"]


def test_valid_env_produces_run_config_with_include_operations_none(tmp_path):
    workspace = make_valid_workspace(tmp_path)
    env_file = write_env(
        tmp_path / ".env",
        f"""
        COMPOSER_ROOT={workspace["COMPOSER_ROOT"]}
        VAULT_ROOT={workspace["VAULT_ROOT"]}
        OUTPUT_ROOT={workspace["OUTPUT_ROOT"]}
        DB_PATH={workspace["DB_PATH"]}
        """,
    )
    env = load_env_with_fallbacks(str(env_file))

    config = create_run_config(env, "run-1")

    assert config.include_operations is None
    assert config.exclude_operations is None
    assert config.target_channels == ["INTERNET"]


def test_include_operations_parse_to_list(tmp_path):
    env_file = write_env(tmp_path / ".env", "INCLUDE_OPERATIONS=A,B")

    env = load_env_with_fallbacks(str(env_file))

    assert env["INCLUDE_OPERATIONS"] == ["A", "B"]


def test_exclude_operations_parse_to_list(tmp_path):
    env_file = write_env(tmp_path / ".env", "EXCLUDE_OPERATIONS=C")

    env = load_env_with_fallbacks(str(env_file))

    assert env["EXCLUDE_OPERATIONS"] == ["C"]


def test_scoped_generation_uses_supported_cli_and_stable_workspace_id(tmp_path, monkeypatch):
    jar = tmp_path / 'mapper.jar'
    jar.touch()
    source = tmp_path / 'source'
    source.mkdir()
    settings = dict(COMPOSER_MAPPER_JAR=str(jar), COMPOSER_ROOT=str(source),
                    VAULT_ROOT=str(tmp_path / 'new-vault'), COMPOSER_MAPPER_VAULT_LAYOUT='scoped',
                    SOURCE_WORKSPACE_ID='enterprise', RUN_MODE='single_channel', TARGET_CHANNELS=['SME'])
    commands = []
    monkeypatch.setattr('workspace_intake.subprocess.run',
                        lambda command, **kwargs: commands.append(command) or SimpleNamespace(returncode=0))
    assert run_composer_mapper(settings) == 0
    assert commands == [['java', '-jar', str(jar), '--root', str(source), '--vault', settings['VAULT_ROOT'],
                         '--vault-layout', 'scoped', '--workspace-id', 'enterprise', '--md', 'true', '--channel', 'SME']]
    settings['SOURCE_WORKSPACE_ID'] = None
    with pytest.raises(ValueError, match='stable SOURCE_WORKSPACE_ID'):
        run_composer_mapper(settings)
    assert len(commands) == 1


def test_mapper_refuses_existing_or_source_output(tmp_path):
    from tools.workspace_intake_tools.mapper_generation import validate_mapper_output
    jar = tmp_path / 'mapper.jar'
    jar.touch()
    source = tmp_path / 'source'
    source.mkdir()
    settings = dict(COMPOSER_MAPPER_JAR=str(jar), COMPOSER_ROOT=str(source), VAULT_ROOT=str(source / 'vault'))
    assert any('separate' in error for error in validate_mapper_output(settings)[0])
    settings['VAULT_ROOT'] = str(tmp_path / 'existing')
    existing = Path(settings['VAULT_ROOT'])
    existing.mkdir()
    (existing / 'evidence.md').touch()
    assert any('empty' in error for error in validate_mapper_output(settings)[0])


def test_startup_accepts_fresh_generation_without_legacy_registry(tmp_path):
    from tools.workspace_intake_tools.env_loader import load_env_with_fallbacks
    settings = load_env_with_fallbacks()
    settings.update(make_valid_workspace(tmp_path))
    jar = tmp_path / 'mapper.jar'
    jar.touch()
    settings.update(COMPOSER_MAPPER_JAR=str(jar), VAULT_ROOT=str(tmp_path / 'new-vault'),
                    COMPOSER_MAPPER_VAULT_LAYOUT='scoped', SOURCE_WORKSPACE_ID='enterprise', ENABLE_GIT=False)
    assert validate_startup(settings) == []
