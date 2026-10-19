"""Exercise real bank Mapper/intake evidence with explicitly controlled workflow fixtures."""

import hashlib
import json
from pathlib import Path
import pytest
from tests.test_intake_plan import setup

from models.common_models import RunConfig
from runtime.configuration import load_configuration
from runtime.pipeline_runner import run_pipeline
from runtime.operation_coordinator import run_operations
from runtime.human_gates import evaluate_gate
from runtime.intake_plan import dependency_plan_context
from runtime.workspace_paths import run_database_path, write_run_report
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.runs import get_run, update_run_status
from tools.state_store_tools.operation_calls import load_graph, get_contract
from tools.state_store_tools.operation_progress import save_progress, progress_rows
from tools.state_store_tools.service_api_uses import list_service_uses
from tools.conversion_tools.operation_call_closure import resolve_operation_calls
from runtime.behavior_conversion.operation_calls import verify_operation_contracts


LEAF = 'GetClientLinksOp'
MIDDLE = 'ValidateClientLinksOp'
TOP = 'GetClientOverviewOp'


def controlled_bank_workflow(trace):
    """Return an explicit offline converter substitute; it does not generate a microservice."""
    def workflow(conn, config, profile, directory, *, execution_plan):
        packets = [packet for batch in execution_plan.batches for packet in batch.task_packets]
        assert len(packets) == 1
        packet = packets[0]
        key = packet.channel + '/' + packet.operation_id
        graph = load_graph(conn, config.run_id)
        steps = [call['step'] for call in graph['calls'] if call['caller'] == key]
        calls, issues = resolve_operation_calls(conn, config.run_id, packet.operation_id, packet.channel, steps, profile)
        assert not issues
        assert len(calls) == len(steps)
        verify_operation_contracts(conn, config, calls)
        trace.append(('start', config.run_id, key, [call['callee'] for call in calls]))
        for number in range(1, 5):
            report = 'Controlled fixture gate for ' + key + ': ' + str(number)
            write_run_report(directory, f'gate_{number}_report.txt', report)
            assert evaluate_gate(conn, config.run_id, number, report, profile.gate_policies[str(number)], True) == 'approved'
        save_progress(conn, config.run_id, key, 'workflow_completed', 'operation_workflow_completed')
        update_run_status(conn, config.run_id, 'paused', 'operation_workflow_completed')
        trace.append(('finish', config.run_id, key, []))
    return workflow


def controlled_publication(trace):
    """Create labelled fixture APIs from the real mapped formats, never a claimed live service."""
    def publish(conn, config, profile, key, directory):
        native = get_contract(conn, config.run_id, key)
        channel, operation = key.split('/', 1)
        artifact = directory / 'controlled-fixture.txt'
        artifact.write_text('Controlled conversion fixture; not executable microservice code.')
        trace.append(('publish', config.run_id, key, []))
        return dict(application_id=profile.source_workspace_id, channel=channel, operation_id=operation,
            api_revision='controlled-fixture-' + operation, service_id=key, artifact_reference=str(artifact),
            method=native['method'], path=native['path'], media_types=[native['media_type']],
            request_contract=native['formats']['csRequestFormat'], response_contract=native['formats']['csReplyFormat'],
            error_contract=native['formats']['csErrorReplyFormat'], api_definition=dict(format='controlled-fixture',
                artifact_evidence=dict(root=str(directory), files={artifact.name: hashlib.sha256(artifact.read_bytes()).hexdigest()})),
            addresses={profile.deployment_environment: dict(base_url_property=native['base_url_property'])},
            completion=dict(source_run_id=config.run_id, validation_report_reference='controlled fixture only',
                conversion_passed=True, package_passed=True, tests_passed=True, review_approved=True, gates_approved=True))
    return publish


def test_real_bank_intake_then_separate_run_reuses_published_leaf(tmp_path):
    root = Path(__file__).resolve().parents[2]
    if not (root / 'source/composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar').is_file():
        pytest.skip('Build Composer Mapper before running bank intake integration')
    base = load_configuration(root / 'configs/bank_operation_calls_validation.yaml')
    from runtime.java_toolchain import resolve_java_home
    try:
        base.java_home = resolve_java_home(base.java_version,
            base.java_home if base.java_home and Path(base.java_home).is_dir() else None)
    except ValueError:
        pytest.skip('Install the configured JDK before running bank intake integration')
    base = base.model_copy(update=dict(output_root=str(tmp_path / 'runs'),
        source_workspace_id='bank-stage-five-fixture', service_registry_path=str(tmp_path / 'registry/services.db'),
        model_provider='mock', plan_approval_policy='automatic',
        gate_policies={str(number): 'automatic' for number in range(1,5)}))
    trace = []
    revision = None
    for run_id, selected in [('leaf-run', [LEAF]), ('caller-run', [MIDDLE, TOP])]:
        profile = base.model_copy(update={'include_operations': selected})
        directory = run_pipeline(profile, run_id)
        conn = get_connection(str(run_database_path(directory)))
        try:
            run = get_run(conn, run_id)
            assert run['current_phase'] == 'conversion_plan_approved'
            config = RunConfig.model_validate(run['run_config_json'])
            context = dependency_plan_context(conn, run_id)
            assert context['order'] == ['INTERNET/' + operation for operation in selected]
            if run_id == 'caller-run':
                assert context['preflight']['reused_services']['INTERNET/' + LEAF]['api_revision'] == revision
            run_operations(conn, config, profile, directory, workflow=controlled_bank_workflow(trace),
                           publication_builder=controlled_publication(trace))
            assert get_run(conn, run_id)['status'] == 'completed'
            assert len(progress_rows(conn, run_id)) == len(selected)
            leaf = next(use for use in list_service_uses(conn, run_id) if use.contract.operation_id == LEAF)
            assert leaf.contract.completion.source_run_id == 'leaf-run'
            revision = leaf.contract.api_revision
            assert len(conn.execute('PRAGMA database_list').fetchall()) == 1
        finally:
            conn.close()
    assert [(kind, key) for kind, run_id, key, calls in trace] == [
        (kind, 'INTERNET/' + operation) for operation in (LEAF, MIDDLE, TOP) for kind in ('start','finish','publish')]
    assert set(trace[-3][3]) == {'INTERNET/' + LEAF, 'INTERNET/' + MIDDLE}
    assert len(list(tmp_path.rglob('migration.db'))) == 2
    assert (tmp_path / 'registry/services.db').is_file()

def test_verification_timeout_pauses_checkpoint_without_discarding_acceptance(setup):
    import importlib.util
    from tools.state_store_tools.operation_progress import initialize_progress
    from tools.state_store_tools.behavior_units import initialize, save, snapshot
    conn, config, profile, directory, operations = setup
    initialize_progress(conn, config.run_id, ['INTERNET/C','INTERNET/B','INTERNET/A'])
    save_progress(conn, config.run_id, 'INTERNET/C', 'running', 'operation_pending')
    initialize(conn)
    save(conn, config.run_id, 'unit', 'accepted-request-format', 'verified-fixture', {'retained': True})
    update_run_status(conn, config.run_id, 'in_progress', 'conversion_pending')
    path = Path(__file__).resolve().parents[2] / 'work/stage-five-validation/verify_bank_demo.py'
    spec = importlib.util.spec_from_file_location('bounded_bank_verification', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.pause_interrupted_run(directory)
    assert get_run(conn, config.run_id)['status'] == 'paused'
    assert progress_rows(conn, config.run_id)[0]['phase'] == 'conversion_pending'
    assert progress_rows(conn, config.run_id)[0]['status'] == 'paused'
    assert json.loads(snapshot(conn, config.run_id, 'unit', 'accepted-request-format')['data_json']) == {'retained': True}


