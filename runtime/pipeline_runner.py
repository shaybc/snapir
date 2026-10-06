"""Execute the deterministic intake stages using existing migration tools."""

import json
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
from runtime.workspace_paths import resolve_run_directory
from tools.source_discovery_tools import discover_java_sources
from tools.source_discovery_tools.classpath import discover_java_classpath


def run_pipeline(profile: PipelineConfiguration, run_id: str) -> Path:
    """Create a new run and prepare planning inputs; fail on an existing run directory."""
    directory = resolve_run_directory(profile.output_root, run_id)
    directory.mkdir(parents=True, exist_ok=False)
    vault = directory / "vault"
    database = directory / "migration.db"
    settings = {key: getattr(constants, key) for key in dir(constants) if key.isupper()}
    settings.update(
        COMPOSER_ROOT=profile.source_root, VAULT_ROOT=str(vault),
        OUTPUT_ROOT=str(directory / "generated"), DB_PATH=str(database),
        RUN_MODE="single_channel" if len(profile.channels) == 1 else "multi_channel",
        TARGET_CHANNELS=profile.channels, TARGET_LANGUAGES=profile.target_languages,
        INCLUDE_OPERATIONS=profile.include_operations, EXCLUDE_OPERATIONS=profile.exclude_operations,
        AGENT_MODEL=profile.model_name, LITELLM_BASE_URL=profile.model_base_url,
        MAX_OPERATIONS_PER_BATCH=profile.max_operations_per_batch,
    )
    config = create_run_config(settings, run_id)
    config.auto_rerun_impacted_operations = profile.auto_rerun_impacted_operations
    conn = get_connection(str(database))
    try:
        create_all_tables(conn)
        persist_run_config(conn, config)
        (directory / "profile.json").write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        source_index = discover_java_sources(profile.source_root)
        (directory / "java_source_index.json").write_text(source_index.model_dump_json(indent=2), encoding="utf-8")
        if source_index.issues:
            raise ValueError("Java source discovery reported issues; inspect java_source_index.json")
        classpath = discover_java_classpath(profile.source_root, profile.classpath_jars,
                                           profile.eclipse_classpath_variables)
        (directory / "java_classpath_index.json").write_text(classpath.model_dump_json(indent=2), encoding="utf-8")
        command = ["java", "-jar", profile.mapper_jar, "--root", profile.source_root,
                   "--vault", str(vault), "--md"]
        if len(profile.channels) == 1:
            command.extend(["--channel", profile.channels[0]])
        update_run_status(conn, run_id, "in_progress", "mapper")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        (directory / "mapper.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError("Composer mapper failed; see mapper.log")
        analysis = run_legacy_composer_analysis(conn, config)
        if analysis["paused"]:
            return directory
        build_all_context_hierarchies(conn, run_id)
        run_shared_artifact_classification(conn, run_id)
        operations = get_operations_for_planning(conn, run_id)
        (directory / "planning_inputs.json").write_text(json.dumps(operations, indent=2), encoding="utf-8")
        update_run_status(conn, run_id, "paused", "planning_inputs_ready")
        return directory
    except Exception:
        update_run_status(conn, run_id, "failed", "intake_failed")
        raise
    finally:
        conn.close()
