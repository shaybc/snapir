from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

from constants import SUPPORTED_TARGET_LANGUAGES
from models.common_models.common import RunMode, TargetLanguage
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.runs import get_run
from tools.workspace_intake_tools.channel_validator import validate_channel_in_registry
from tools.workspace_intake_tools.db_initializer import initialize_database
from tools.workspace_intake_tools.env_loader import load_env_with_fallbacks
from tools.workspace_intake_tools.run_factory import create_run_config, persist_run_config
from tools.workspace_intake_tools.vault_validator import validate_vault_structure
from tools.workspace_intake_tools.vault_validator import validate_vault_input


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", dest="env_file")
    parser.add_argument("--resume", dest="resume_run_id")
    args = parser.parse_args(argv)

    resolved_env = load_env_with_fallbacks(args.env_file)
    if args.env_file:
        resolved_env["ENV_FILE"] = args.env_file
    run_id = args.resume_run_id or f"run-{uuid.uuid4()}"

    if args.resume_run_id:
        conn = get_connection(resolved_env["DB_PATH"])
        existing = get_run(conn, args.resume_run_id)
        if existing is None:
            print(f"Blocking validation failure: run_id not found for resume: {args.resume_run_id}")
            return 1
        print(f"Resuming run {args.resume_run_id}")
        return 0

    errors = validate_startup(resolved_env)
    if errors:
        for error in errors:
            print(f"Blocking validation failure: {error}")
        return 1

    mapper_result = run_composer_mapper(resolved_env)
    if mapper_result != 0:
        print("Blocking validation failure: composer-mapper failed")
        return 1

    try:
        missing, channels = validate_vault_input(resolved_env["VAULT_ROOT"], resolved_env.get("TARGET_CHANNELS") or [])
        if missing or resolved_env["RUN_MODE"] != RunMode.full_inventory.value and channels:
            raise ValueError(f"Missing vault paths: {missing}; missing channel execution evidence: {channels}")
    except ValueError as exc:
        print(f"Blocking validation failure: {exc}")
        return 1

    warnings = check_warnings(resolved_env)
    for warning in warnings:
        print(f"Warning: {warning}")

    conn = initialize_database(resolved_env["DB_PATH"], run_id)
    config = create_run_config(resolved_env, run_id)
    persist_run_config(conn, config)
    print(
        "RunConfig persisted: "
        f"run_id={config.run_id}, mode={config.run_mode.value}, "
        f"channels={config.target_channels}, languages={[lang.value for lang in config.target_languages]}"
    )
    print("RootMigrationOrchestratorAgent start is deferred until agent package exists.")
    return 0


def validate_startup(resolved_env: dict) -> list[str]:
    errors: list[str] = []
    composer_root = Path(resolved_env["COMPOSER_ROOT"])
    if not composer_root.exists():
        errors.append(f"COMPOSER_ROOT does not exist: {composer_root}")
    elif not any(composer_root.rglob("*.xml")):
        errors.append(f"COMPOSER_ROOT contains no XML files: {composer_root}")

    run_mode = resolved_env["RUN_MODE"]
    if run_mode not in {mode.value for mode in RunMode}:
        errors.append(f"RUN_MODE is not supported: {run_mode}")

    target_channels = resolved_env.get("TARGET_CHANNELS") or []
    if run_mode == RunMode.single_channel.value and len(target_channels) != 1:
        errors.append("single_channel requires exactly one TARGET_CHANNELS value")
    if run_mode == RunMode.multi_channel.value and len(target_channels) == 0:
        errors.append("multi_channel requires one or more TARGET_CHANNELS values")

    supported_languages = set(SUPPORTED_TARGET_LANGUAGES)
    for language in resolved_env.get("TARGET_LANGUAGES") or []:
        if language not in supported_languages:
            errors.append(f"TARGET_LANGUAGE is not supported: {language}")

    from tools.workspace_intake_tools.mapper_generation import validate_mapper_output
    generation_errors, will_generate = validate_mapper_output(resolved_env)
    errors.extend(generation_errors)
    try:
        missing_vault_paths, missing_channels = ([], []) if will_generate else validate_vault_input(
            resolved_env["VAULT_ROOT"], target_channels)
    except ValueError as exc:
        errors.append(str(exc))
        missing_vault_paths = [resolved_env["VAULT_ROOT"]]
    for path in missing_vault_paths:
        errors.append(f"Required vault path missing: {path}")

    if run_mode != RunMode.full_inventory.value and not missing_vault_paths and not will_generate:
        for channel in missing_channels:
            errors.append(f"TARGET_CHANNEL not found in channel registry: {channel}")

    if resolved_env.get("ENABLE_GIT") and not (Path.cwd() / ".git").exists():
        errors.append("ENABLE_GIT=true but current workspace is not a Git repository")

    return errors


def run_composer_mapper(resolved_env: dict) -> int:
    jar = resolved_env.get("COMPOSER_MAPPER_JAR")
    if not jar or not Path(jar).exists():
        return 0
    from tools.workspace_intake_tools.mapper_generation import mapper_command
    command = mapper_command(resolved_env)
    return subprocess.run(command, check=False).returncode


def check_warnings(resolved_env: dict) -> list[str]:
    warnings: list[str] = []
    try:
        request = Request(resolved_env["LITELLM_BASE_URL"], method="GET")
        urlopen(request, timeout=2)
    except Exception:
        warnings.append("model endpoint is not reachable")
    return warnings


if __name__ == "__main__":
    raise SystemExit(main())
