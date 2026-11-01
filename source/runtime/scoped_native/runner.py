"""Prepare qualified execution, preserve human gates, and reuse native conversion."""

import json
from pathlib import Path
from time import perf_counter

from runtime.scoped_conversion import prepare_scoped_runtime
from runtime.scoped_native.payloads import native_inputs
from runtime.scoped_native.scope import native_execution
from runtime.workspace_paths import write_run_report, run_report_path
from tools.state_store_tools.runs import update_run_status
from runtime.behavior_conversion.resume_budget import with_resume_budget


@with_resume_budget
def resume_scoped_pipeline(conn, config, profile, directory, *, plan=None, model_call=None, context_factory=None):
    """Opt in to the verified behavior-unit capability; unsupported paths stay blocked."""
    if model_call is None:profile=profile.model_copy(update={'staged_unit_conversion':True})
    report = prepare_scoped_runtime(conn, config, profile, directory, plan=plan)
    if getattr(profile, 'scoped_native_mode', 'prepare') == 'prepare':
        return Path(directory)
    if profile.conversion_strategy != 'behavior_units' or profile.scoped_native_mode not in {'behavior_units_v1', 'component_first_v1'}:
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
    if profile.scoped_native_mode == 'component_first_v1':
        from runtime.component_conversion.runner import convert_basic_components
        convert_basic_components(conn, config, profile, directory, report, classpath,
                                        model_call=model_call, context_factory=factory, include_steps=True, include_formats=True)
        component_report = json.loads(run_report_path(directory,'component-generation.json').read_text(encoding='utf-8'))
        if any(item['status'] in {'incomplete','deferred'} for item in component_report['groups'].values()):
            return Path(directory)
        update_run_status(conn,config.run_id,'in_progress','conversion_units_verifying')
    component_provider = None
    from runtime.scoped_native.project_names import native_artifact_id
    native_factory = lambda settings, project, artifact: create_native_context(config, settings, project, factory,
        artifact_id=native_artifact_id(Path(project).name))
    started = perf_counter()
    try:
        if profile.scoped_native_mode == 'component_first_v1':
            from runtime.component_conversion.unit_provider import ComponentUnitProvider
            component_provider = ComponentUnitProvider(conn,config,profile,report,classpath,factory,model_call)
        with native_execution(conn, config, profile, classpath, by_operation):
            _convert_and_review(conn, config, profile, directory, closures, by_operation, units, bindings,
                                native_factory, model_call, execution_plan=plan, component_provider=component_provider)
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
        counts = {}
        complete = False
        if profile.scoped_native_mode == 'component_first_v1':
            from runtime.behavior_conversion.verification_state import write_verification_results
            from runtime.scoped_native.results import verify_operation
            counts = dict(accepted_operations=0)
            for row in conn.execute("SELECT identity,data_json FROM behavior_snapshots WHERE run_id=? AND category='operation' AND status='accepted'",(config.run_id,)):
                if row['identity'] not in by_operation:
                    continue
                try:
                    verify_operation(conn,config,profile,row['identity'],json.loads(row['data_json']))
                    counts['accepted_operations'] += 1
                except (ValueError,OSError):
                    pass
            results = write_verification_results(conn,config,directory,units)
            counts.update(unit_verification=results['counts'],pending_units=len(results['pending_unit_ids']))
            complete = bool(units and results['counts']['accepted']==len(units) and
                counts['accepted_operations']==len(by_operation) and conn.execute(
                    'SELECT status FROM runs WHERE run_id=?',(config.run_id,)).fetchone()[0]=='completed')
        write_run_report(directory, 'scoped_native_execution.json', json.dumps(dict(
            run_id=config.run_id, capability='component-first-cf7' if profile.scoped_native_mode=='component_first_v1' else 'scoped-behavior-v1', conversion_enabled=True,
            acceptance_complete=complete, phase=phase, selected_contexts=sorted(by_operation),
            configured_units=len(units), elapsed_seconds=perf_counter() - started,**counts), indent=2))
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
