"""Prepare qualified execution, preserve human gates, and reuse native conversion."""

import json
from pathlib import Path
from time import perf_counter

from runtime.scoped_conversion import prepare_scoped_runtime
from runtime.scoped_native.payloads import native_inputs
from runtime.scoped_native.scope import native_execution
from runtime.workspace_paths import write_run_report
from tools.state_store_tools.runs import update_run_status
from runtime.behavior_conversion.resume_budget import with_resume_budget


@with_resume_budget
def resume_scoped_pipeline(conn, config, profile, directory, *, plan=None, model_call=None, context_factory=None):
    """Opt in to the verified behavior-unit capability; unsupported paths stay blocked."""
    report = prepare_scoped_runtime(conn, config, profile, directory, plan=plan)
    if getattr(profile, 'scoped_native_mode', 'prepare') == 'prepare':
        return Path(directory)
    if profile.conversion_strategy != 'behavior_units' or profile.scoped_native_mode != 'behavior_units_v1':
        update_run_status(conn, config.run_id, 'blocked', 'conversion_scoped_unsupported')
        return Path(directory)
    if report.get('preparation_error') or not report['operations'] or any(
            item['status'] != 'prepared' for item in report['operations'].values()):
        return Path(directory)
    from runtime.behavior_conversion.runner import _convert_and_review, _gate
    from runtime.behavior_conversion.ownership import create_native_context
    from runtime.managed_projects import create_build_context
    from tools.source_discovery_tools.classpath import discover_java_classpath
    from tools.state_store_tools.behavior_units import initialize
    closures, by_operation, units, bindings = native_inputs(report)
    output_root = Path(config.output_root).resolve()
    if any(not (output_root / key).resolve().is_relative_to(output_root) for key in by_operation):
        raise ValueError('Scoped native project is outside the run output root')
    plan = _execution_plan(conn, config, closures, plan)
    from runtime.scoped_native.plan_approval import approve_plan
    if not approve_plan(conn, config, profile, directory, plan):
        return Path(directory)
    gate = json.dumps(dict(capability='scoped-behavior-v1', contexts={key: dict(
        evidence_hash=item['behavior_request']['evidence_hash'], units=sorted(unit.unit_id for unit in by_operation[key]))
        for key, item in report['operations'].items()}), sort_keys=True)
    if not _gate(conn, config, profile, directory, 1, gate, True, 'conversion_pending'):
        return Path(directory)
    initialize(conn)
    classpath = discover_java_classpath(config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables)
    factory = context_factory or create_build_context
    from runtime.scoped_native.project_names import native_artifact_id
    native_factory = lambda settings, project, artifact: create_native_context(config, settings, project, factory,
        artifact_id=native_artifact_id(Path(project).name))
    started = perf_counter()
    try:
        with native_execution(conn, config, profile, classpath, by_operation):
            _convert_and_review(conn, config, profile, directory, closures, by_operation, units, bindings,
                                native_factory, model_call, execution_plan=plan)
    except Exception as exc:
        from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale
        if isinstance(exc, ScopedCheckpointStale):
            write_run_report(directory, 'scoped_workflow_preparation.json', json.dumps(dict(
                report, stale_contexts=exc.affected, preparation_error=str(exc)), indent=2))
            update_run_status(conn, config.run_id, 'blocked', 'conversion_scoped_stale')
            raise
        update_run_status(conn, config.run_id, 'failed', 'conversion_scoped_native_failed')
        raise
    finally:
        phase = conn.execute('SELECT current_phase FROM runs WHERE run_id=?', (config.run_id,)).fetchone()[0]
        write_run_report(directory, 'scoped_native_execution.json', json.dumps(dict(
            run_id=config.run_id, capability='scoped-behavior-v1', conversion_enabled=True,
            acceptance_complete=False, phase=phase, selected_contexts=sorted(by_operation),
            configured_units=len(units), elapsed_seconds=perf_counter() - started), indent=2))
    return Path(directory)


def _execution_plan(conn, config, closures, supplied):
    """Persist a typed selected-context plan without invoking bare-name legacy planning."""
    from models.migration_models import MigrationPlan, MigrationBatch, MigrationTaskPacket
    from agents.migration_planning.agent import write_migration_plan
    if supplied is not None:
        if not isinstance(supplied, MigrationPlan):
            raise ValueError('Native scoped execution requires a typed migration plan')
        packets = [packet for batch in supplied.batches for packet in batch.task_packets]
        keys = [packet.channel + '/' + packet.operation_id for packet in packets]
        expected = {closure['channel'] + '/' + closure['operation_id'] for closure in closures}
        if supplied.run_id != config.run_id or set(keys) != expected or len(keys) != len(expected) or any(
                packet.run_id != config.run_id or packet.target_language.value != 'java' for packet in packets):
            raise ValueError('Native plan differs from the selected scoped execution contexts')
        write_migration_plan(conn, supplied)
        return supplied
    packets = [MigrationTaskPacket(task_id='scoped-' + closure['operation_identity'], run_id=config.run_id,
        operation_id=closure['operation_id'], channel=closure['channel'], target_language='java',
        group=('branch_heavy' if any(len(edges) > 1 for edges in closure['routing_graph'].values()) else
               'one_step' if len(closure['routing_graph']) == 1 else 'multi_step_linear'), status='pending') for closure in closures]
    plan = MigrationPlan(plan_id='scoped-native-' + config.run_id, run_id=config.run_id,
        batches=[MigrationBatch(batch_id='scoped-native', run_id=config.run_id, task_packets=packets,
            is_pilot=True, status='pending')], total_operations=len(packets), unusual_count=0, status='pending')
    write_migration_plan(conn, plan)
    return plan
