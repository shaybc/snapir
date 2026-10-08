from __future__ import annotations

from pathlib import Path

from tools.workspace_intake_tools.channel_validator import validate_channel_in_registry
from tools.workspace_intake_tools.env_loader import load_env_with_fallbacks
from tools.workspace_intake_tools.run_factory import create_run_config
from workspace_intake import validate_startup


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
