from __future__ import annotations

from pathlib import Path
import sqlite3

from models.common_models.common import RunConfig
from tools.state_store_tools.runs import upsert_run
from runtime.workspace_paths import resolve_run_directory, run_report_path


def create_run_config(resolved_env: dict, run_id: str) -> RunConfig:
    return RunConfig(
        run_id=run_id,
        run_mode=resolved_env["RUN_MODE"],
        source_root=resolved_env["COMPOSER_ROOT"],
        vault_root=resolved_env["VAULT_ROOT"],
        output_root=resolved_env["OUTPUT_ROOT"],
        db_path=resolved_env["DB_PATH"],
        env_file=resolved_env.get("ENV_FILE"),
        target_channels=resolved_env.get("TARGET_CHANNELS") or [],
        composer_mapper_channel_filter=_composer_mapper_channel_filter(resolved_env),
        target_languages=resolved_env.get("TARGET_LANGUAGES") or [],
        enable_git=resolved_env["ENABLE_GIT"],
        artifact_schema_version=resolved_env["ARTIFACT_SCHEMA_VERSION"],
        max_agent_task_retries=resolved_env["MAX_AGENT_TASK_RETRIES"],
        max_parallel_conversion_workers=resolved_env["MAX_PARALLEL_CONVERSION_WORKERS"],
        max_parallel_llm_tasks=resolved_env["MAX_PARALLEL_LLM_TASKS"],
        max_parallel_build_tasks=resolved_env["MAX_PARALLEL_BUILD_TASKS"],
        max_operations_per_batch=resolved_env["MAX_OPERATIONS_PER_BATCH"],
        model_name=resolved_env["AGENT_MODEL"],
        model_base_url=resolved_env["LITELLM_BASE_URL"],
        auto_rerun_impacted_operations=True,
        include_operations=resolved_env.get("INCLUDE_OPERATIONS"),
        exclude_operations=resolved_env.get("EXCLUDE_OPERATIONS"),
    )


def persist_run_config(conn: sqlite3.Connection, config: RunConfig, directory: Path | None = None) -> None:
    """Persist effective settings in the database and the run inspection reports."""
    directory = directory if directory is not None else resolve_run_directory(config.output_root, config.run_id)
    snapshot = run_report_path(directory, "run_config.json")
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    upsert_run(
        conn,
        run_id=config.run_id,
        run_mode=config.run_mode.value,
        status="started",
        current_phase="startup",
        run_config=config,
        schema_version=config.schema_version,
    )


def _composer_mapper_channel_filter(resolved_env: dict) -> str | None:
    channels = resolved_env.get("TARGET_CHANNELS") or []
    if resolved_env.get("RUN_MODE") == "single_channel" and len(channels) == 1:
        return channels[0]
    return None
