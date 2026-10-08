"""Execute the deterministic intake stages using existing migration tools."""

from copy import deepcopy
import json
import logging
import subprocess
from pathlib import Path

import constants
from agents.legacy_composer_analysis.agent import run_legacy_composer_analysis
from agents.migration_planning.agent import get_operations_for_planning
from models.pipeline_configuration import PipelineConfiguration
from tools.conversion_tools.context_hierarchy_resolver_tool import build_all_context_hierarchies
from tools.shared_artifact_classifier_tools.classifier import run_shared_artifact_classification
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.runs import update_run_status
from tools.workspace_intake_tools.run_factory import create_run_config, persist_run_config
from runtime.workspace_paths import resolve_run_directory, run_database_path, run_profile_path, run_report_path, run_mapper_log_path
from tools.source_discovery_tools import discover_java_sources
from tools.source_discovery_tools.classpath import discover_java_classpath
from runtime.model_execution.readiness import intake_model_warning
from runtime.java_toolchain import java_scope, java_environment, run_java


def run_pipeline(profile: PipelineConfiguration, run_id: str) -> Path:
    """Create a new run and prepare planning inputs; fail on an existing run directory."""
    logger = logging.getLogger(__name__)
    logger.info("Starting workspace intake.")
    warning = intake_model_warning(profile)
    if warning:
        print(warning)
    directory = resolve_run_directory(profile.output_root, run_id)
    directory.mkdir(parents=True, exist_ok=False)
    for folder in ("state", "reports", "logs", "generated"):
        (directory / folder).mkdir()
    from runtime.workflow_stages import REPORT_FOLDERS
    for stage in REPORT_FOLDERS.values():
        (directory / "reports" / stage).mkdir()
    vault = directory / "vault"
    database = run_database_path(directory)
    settings = {key: deepcopy(getattr(constants, key)) for key in dir(constants) if key.isupper()}
    settings.update(
        COMPOSER_ROOT=profile.source_root, VAULT_ROOT=str(vault),
        OUTPUT_ROOT=str(directory / "generated"), DB_PATH=str(database),
        RUN_MODE="single_channel" if len(profile.channels) == 1 else "multi_channel",
        TARGET_CHANNELS=profile.channels, TARGET_LANGUAGES=profile.target_languages,
        INCLUDE_OPERATIONS=profile.include_operations, EXCLUDE_OPERATIONS=profile.exclude_operations,
        AGENT_MODEL=profile.model_name, LITELLM_BASE_URL=profile.model_base_url,
        MAX_OPERATIONS_PER_BATCH=profile.max_operations_per_batch,
        MAX_AGENT_TASK_RETRIES=profile.max_agent_task_retries,
        MAX_PARALLEL_CONVERSION_WORKERS=profile.max_parallel_conversion_workers,
        MAX_PARALLEL_LLM_TASKS=profile.max_parallel_llm_tasks,
        MAX_PARALLEL_BUILD_TASKS=profile.max_parallel_build_tasks,
        INTER_BATCH_DELAY_SECS=profile.inter_batch_delay_secs,
        ENABLE_GIT=profile.enable_git,
        AUTO_RERUN_IMPACTED_OPERATIONS=profile.auto_rerun_impacted_operations,
    )
    config = create_run_config(settings, run_id)
    conn = get_connection(str(database))
    try:
        toolchain = java_scope(profile)
        toolchain.__enter__()
        create_all_tables(conn)
        persist_run_config(conn, config, directory)
        run_profile_path(directory).write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Discovering Java sources and classpath.")
        source_index = discover_java_sources(profile.source_root)
        run_report_path(directory, "java_source_index.json").write_text(source_index.model_dump_json(indent=2), encoding="utf-8")
        if source_index.issues:
            raise ValueError("Java source discovery reported issues; inspect reports/1_intake_and_legacy_analysis/java_source_index.json")
        classpath = discover_java_classpath(profile.source_root, profile.classpath_jars,
                                           profile.eclipse_classpath_variables)
        run_report_path(directory, "java_classpath_index.json").write_text(classpath.model_dump_json(indent=2), encoding="utf-8")
        from tools.component_inventory_tools import build_component_inventory
        from tools.state_store_tools.component_inventory import persist_component_inventory, get_implementation_usage, get_configured_component_usage
        logger.info("Building component inventory.")
        inventory = build_component_inventory(profile.source_root, profile.source_workspace_id, source_index)
        persist_component_inventory(conn, run_id, inventory)
        run_report_path(directory, "component_inventory.json").write_text(inventory.model_dump_json(indent=2), encoding="utf-8")
        run_report_path(directory, "java_source_dependencies.json").write_text(inventory.java_dependencies.model_dump_json(indent=2), encoding="utf-8")
        run_report_path(directory, "component_usage.json").write_text(json.dumps(get_implementation_usage(conn, run_id), indent=2), encoding="utf-8")
        run_report_path(directory, "configured_component_usage.json").write_text(json.dumps(get_configured_component_usage(conn, run_id), indent=2), encoding="utf-8")
        command = ["java", "-jar", profile.mapper_jar, "--root", profile.source_root,
                   "--vault", str(vault), "--md"]
        if len(profile.channels) == 1:
            command.extend(["--channel", profile.channels[0]])
        update_run_status(conn, run_id, "in_progress", "mapper")
        logger.info("Running Composer mapper; output is saved in logs/mapper.log.")
        result = run_java(command, capture_output=True, text=True, check=False,
                                env=java_environment(constants.MAPPER_JAVA_VERSION))
        run_mapper_log_path(directory).write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError("Composer mapper failed; see logs/mapper.log")
        logger.info("Importing and analyzing the legacy vault.")
        analysis = run_legacy_composer_analysis(conn, config)
        if analysis["paused"]:
            return directory
        logger.info("Preparing context hierarchies and planning inputs.")
        build_all_context_hierarchies(conn, run_id)
        run_shared_artifact_classification(conn, run_id)
        operations = get_operations_for_planning(conn, run_id)
        run_report_path(directory, "planning_inputs.json").write_text(json.dumps(operations, indent=2), encoding="utf-8")
        update_run_status(conn, run_id, "paused", "planning_inputs_ready")
        return directory
    except Exception:
        update_run_status(conn, run_id, "failed", "intake_failed")
        raise
    finally:
        if "toolchain" in locals():
            toolchain.__exit__(None, None, None)
        conn.close()
