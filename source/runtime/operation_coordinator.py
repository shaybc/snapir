"""Invoke the existing native workflow sequentially using the approved run plan."""

import json
import hashlib
from pathlib import Path

from models.migration_models import MigrationPlan
from runtime.human_gates import operation_gate_scope
from runtime.intake_plan import dependency_plan_context
from runtime.service_publication import prepare_publication, verify_publication_artifacts
from tools.converted_service_registry_tools.location import resolve_registry_settings
from tools.converted_service_registry_tools.registry import open_registry, publish_service
from tools.state_store_tools.operation_progress import initialize_progress, progress_rows, save_progress, operation_directory
from tools.state_store_tools.service_api_uses import record_service_use
from tools.state_store_tools.runs import update_run_status, get_run


def execution_view(plan, operation):
    """Make a one-operation view without replacing the saved full plan or creating a run."""
    batches = [batch.model_copy(update={'task_packets': [packet for packet in batch.task_packets
        if packet.channel + '/' + packet.operation_id == operation]}) for batch in plan.batches]
    batches = [batch for batch in batches if batch.task_packets]
    if sum(len(batch.task_packets) for batch in batches) != 1:
        raise ValueError('Operation must occur exactly once in the approved plan')
    return plan.model_copy(update={'batches': batches, 'total_operations': 1,
        'unusual_count': sum(packet.group.value == 'unusual_manual_review' for batch in batches for packet in batch.task_packets)})


def run_operations(conn, config, profile, directory, *, workflow=None, publication_builder=None):
    """Complete, publish and checkpoint one operation before invoking any caller.

    Injected workflow/publication functions support offline development checks;
    production defaults invoke the existing converter and finalization evidence.
    """
    from runtime.intake_plan import resume_intake_plan
    if resume_intake_plan(conn, config, profile, directory) != 'approved':
        return directory
    context = dependency_plan_context(conn, config.run_id)
    row = conn.execute('SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1', (config.run_id,)).fetchone()
    plan = MigrationPlan.model_validate_json(row[0])
    snapshot = conn.execute('SELECT snapshot_json FROM intake_conversion_plans WHERE run_id=?', (config.run_id,)).fetchone()[0]
    initialize_progress(conn, config.run_id, context['order'], plan_hash=hashlib.sha256(snapshot.encode()).hexdigest())
    for contract in context['preflight']['reused_services'].values():
        record_service_use(conn, config.run_id, contract, profile.deployment_environment)
    if workflow is None:
        from runtime.behavior_conversion.runner import resume_behavior_pipeline
        workflow = resume_behavior_pipeline
    publication_builder = publication_builder or prepare_publication
    _, registry_path = resolve_registry_settings(profile)
    registry = open_registry(registry_path)
    try:
        for progress in progress_rows(conn, config.run_id):
            if progress['status'] == 'completed':
                continue
            key = progress['operation_key']
            channel, operation = key.split('/', 1)
            folder = operation_directory(directory, key)
            folder.mkdir(parents=True, exist_ok=True)
            scoped_config = config.model_copy(update={'target_channels': [channel], 'include_operations': [operation]})
            view = execution_view(plan, key)
            print('Converting operation: ' + key + '; reports: ' + str(folder / 'reports'))
            try:
                with operation_gate_scope(key):
                    if progress['status'] not in {'workflow_completed', 'publication_pending'}:
                        save_progress(conn, config.run_id, key, 'running', progress['phase'])
                        update_run_status(conn, config.run_id, 'in_progress', progress['phase'])
                        workflow(conn, scoped_config, profile, folder, execution_plan=view)
                        run = get_run(conn, config.run_id)
                        if run['current_phase'] != 'operation_workflow_completed':
                            save_progress(conn, config.run_id, key, 'paused', run['current_phase'])
                            return directory
                        save_progress(conn, config.run_id, key, 'workflow_completed', 'operation_workflow_completed')
                    if progress['publication_json']:
                        publication = json.loads(progress['publication_json'])
                    else:
                        update_run_status(conn, config.run_id, 'paused', 'operation_workflow_completed')
                        publication = publication_builder(conn, scoped_config, profile, key, folder)
                        save_progress(conn, config.run_id, key, 'publication_pending', 'operation_publication_pending', publication)
                    verify_publication_artifacts(publication)
                    published = publish_service(registry, publication)
                    record_service_use(conn, config.run_id, published, profile.deployment_environment)
                    save_progress(conn, config.run_id, key, 'completed', 'operation_completed', publication)
                    print('Operation completed and published: ' + key)
            except Exception:
                current = next(item for item in progress_rows(conn, config.run_id) if item['operation_key'] == key)
                failure_phase = get_run(conn, config.run_id)['current_phase']
                if current['status'] not in {'workflow_completed', 'publication_pending'}:
                    save_progress(conn, config.run_id, key, 'failed', failure_phase)
                update_run_status(conn, config.run_id, 'failed', 'operation_publication_pending' if current['status'] in {
                    'workflow_completed', 'publication_pending'} else failure_phase)
                raise
        update_run_status(conn, config.run_id, 'completed', 'migration_approved')
        return directory
    finally:
        registry.close()
