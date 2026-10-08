"""Resume a persisted run through planning approval and dependency closure."""

import json
import logging

from agents.migration_planning.agent import build_gate1_report, get_operations_for_planning
from agents.migration_planning.plan_validator import validate_migration_plan
from models.common_models import RunConfig
from models.migration_models import MigrationPlan
from models.pipeline_configuration import PipelineConfiguration
from runtime.human_gates import evaluate_gate
from runtime.planning import prepare_plan
from runtime.workspace_paths import resolve_run_directory, run_database_path, run_profile_path, run_report_path, write_run_report
from tools.conversion_tools.closure_builder_tool import build_operation_closure
from tools.conversion_tools.context_field_resolver_tool import resolve_context_fields
from tools.state_store_tools._json import loads
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.runs import get_run, update_run_status
from tools.source_discovery_tools.classpath import discover_java_classpath
from runtime.model_execution.diagnostics import run_model_diagnostics
from runtime.java_toolchain import java_scope


def resume_pipeline(output_root: str, run_id: str):
    """Resume planning without rerunning intake, stopping on review or blocked closure."""
    directory = resolve_run_directory(output_root, run_id)
    if not run_database_path(directory).is_file():
        raise ValueError("Run database does not exist")
    profile = PipelineConfiguration.model_validate_json(run_profile_path(directory).read_text(encoding="utf-8"))
    conn = get_connection(str(run_database_path(directory)))
    diagnostics = run_model_diagnostics(directory)
    diagnostics.__enter__()
    try:
        toolchain = java_scope(profile)
        toolchain.__enter__()
        run = get_run(conn, run_id)
        if run is None:
            raise ValueError("Run does not exist")
        config = RunConfig.model_validate(run["run_config_json"])
        logging.getLogger(__name__).info("Resuming saved checkpoint: %s (%s).", run["current_phase"], run["status"])
        if run["current_phase"] in {"gate_4_pending", "gate_4_rejected", "finalization_blocked", "migration_approved", "dry_run_complete"}:
            row = conn.execute("SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1", (run_id,)).fetchone()
            if row is None:
                raise ValueError("Finalization requires a persisted migration plan")
            from runtime.finalization import run_finalization
            run_finalization(conn, config, profile, MigrationPlan.model_validate_json(row[0]), directory)
            return directory
        if run["current_phase"] in {"component_review", "component_revision", "component_review_blocked", "gate_2_pending",
                                     "gate_2_rejected", "assembly_pending", "operation_assembly", "assembly_blocked",
                                     "operation_review_pending", "operation_review", "operation_revision", "operation_review_blocked",
                                     "gate_3_pending", "gate_3_rejected", "service_generation_pending", "service_generation",
                                     "service_generation_blocked", "validation_evidence_pending",
                                     "component_correction_pending", "assembly_correction_pending"}:
            row = conn.execute("SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1",
                               (run_id,)).fetchone()
            if row is None:
                raise ValueError("Component review requires a persisted migration plan")
            if run["current_phase"] == "component_correction_pending":
                from runtime.managed_projects import run_managed_tasks
                results = run_managed_tasks(conn, config, profile, MigrationPlan.model_validate_json(row[0]))
                if results["failed"]:
                    update_run_status(conn, run_id, "blocked", "component_correction_pending")
                    return directory
            from runtime.component_review import run_component_review_gate
            phase = run_component_review_gate(conn, config, profile, MigrationPlan.model_validate_json(row[0]), directory)
            if phase == "assembly_pending":
                from runtime.operation_assembly import run_operation_assembly
                phase = run_operation_assembly(conn, config, profile, MigrationPlan.model_validate_json(row[0]), directory)
                if phase == "operation_review_pending":
                    from runtime.operation_review import run_operation_review_gate
                    phase = run_operation_review_gate(conn, config, profile, MigrationPlan.model_validate_json(row[0]), directory)
                    if phase == "service_generation_pending":
                        from runtime.service_generation import run_service_generation
                        phase = run_service_generation(conn, config, profile, MigrationPlan.model_validate_json(row[0]), directory)
                        if phase == "validation_evidence_pending":
                            from runtime.finalization import run_finalization
                            run_finalization(conn, config, profile, MigrationPlan.model_validate_json(row[0]), directory)
            return directory
        if run["current_phase"] not in {"planning_inputs_ready", "planning", "planning_failed", "gate_1_pending",
                                          "gate_1_rejected", "closures_blocked", "conversion_pending"}:
            raise ValueError("This checkpoint cannot yet be resumed by the runtime")
        operations = get_operations_for_planning(conn, run_id)
        logging.getLogger(__name__).info("Loaded %s operations for planning.", len(operations))
        row = conn.execute("SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1",
                           (run_id,)).fetchone()
        if row:
            plan = MigrationPlan.model_validate_json(row[0])
            errors = validate_migration_plan(plan, config, conn)
            if errors:
                raise ValueError("Persisted plan failed validation: " + "; ".join(errors))
        else:
            update_run_status(conn, run_id, "in_progress", "planning")
            try:
                plan = prepare_plan(conn, config, profile, operations)
            except Exception:
                update_run_status(conn, run_id, "failed", "planning_failed")
                raise
        from tools.component_inventory_tools.library_planner import prepare_library_plan
        libraries = prepare_library_plan(conn, config, profile, plan)
        if libraries is not None:
            write_run_report(directory, "shared_library_plan.json", libraries.model_dump_json(indent=2))
        from runtime.gate_one_reports import write_gate_one_reports
        report = write_gate_one_reports(directory, conn, config, profile, plan, operations, libraries)
        decision = evaluate_gate(conn, run_id, 1, report, profile.gate_policies.get("1", "human"), libraries is None or not libraries.diagnostics)
        if decision != "approved":
            update_run_status(conn, run_id, "paused" if decision == "pending" else "stopped", f"gate_1_{decision}")
            return directory
        closures = []
        classpath = discover_java_classpath(config.source_root, profile.classpath_jars,
                                           profile.eclipse_classpath_variables)
        run_report_path(directory, "java_classpath_index.json").parent.mkdir(parents=True, exist_ok=True)
        run_report_path(directory, "java_classpath_index.json").write_text(classpath.model_dump_json(indent=2), encoding="utf-8")
        for batch in plan.batches:
            for packet in batch.task_packets:
                source = conn.execute("SELECT metadata_json FROM source_artifacts WHERE run_id=? AND kind='operation' AND logical_id=?",
                                      (run_id, packet.operation_id)).fetchone()
                metadata = loads(source[0], {}) if source else {}
                context_id = metadata.get("operation_context")
                if context_id:
                    resolve_context_fields(conn, context_id, packet.channel, run_id, config.source_root)
                closure = build_operation_closure(conn, packet.operation_id, packet.channel, run_id,
                                                  config.source_root, config.vault_root, classpath_index=classpath, profile=profile)
                closures.append(closure.model_dump(mode="json"))
        write_run_report(directory, "dependency_closure.json", json.dumps(closures, indent=2))
        blocked = any(item["status"] != "READY" for item in closures)
        update_run_status(conn, run_id, "blocked" if blocked else "paused",
                          "closures_blocked" if blocked else "conversion_pending")
        if not blocked:
            from runtime.managed_projects import enqueue_closure_conversions, run_managed_tasks
            try:
                enqueue_closure_conversions(conn, config, closures)
                results = run_managed_tasks(conn, config, profile, plan)
            except Exception:
                update_run_status(conn, run_id, "failed", "conversion_pending")
                raise
            write_run_report(directory, "managed_conversion_results.json", json.dumps(results, indent=2))
            update_run_status(conn, run_id, "blocked" if results["failed"] else "paused",
                              "conversion_pending")
            if not results["failed"]:
                from runtime.component_review import run_component_review_gate
                update_run_status(conn, run_id, "in_progress", "component_review")
                phase = run_component_review_gate(conn, config, profile, plan, directory)
                if phase == "assembly_pending":
                    from runtime.operation_assembly import run_operation_assembly
                    phase = run_operation_assembly(conn, config, profile, plan, directory)
                    if phase == "operation_review_pending":
                        from runtime.operation_review import run_operation_review_gate
                        phase = run_operation_review_gate(conn, config, profile, plan, directory)
                        if phase == "service_generation_pending":
                            from runtime.service_generation import run_service_generation
                            phase = run_service_generation(conn, config, profile, plan, directory)
                            if phase == "validation_evidence_pending":
                                from runtime.finalization import run_finalization
                                run_finalization(conn, config, profile, plan, directory)
        return directory
    finally:
        if "toolchain" in locals():
            toolchain.__exit__(None, None, None)
        diagnostics.__exit__(None, None, None)
        conn.close()
