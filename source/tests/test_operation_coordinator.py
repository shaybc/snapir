"""Controlled sequential workflow traces without model calls or Maven processes."""

import copy
import hashlib
import json
import pytest

from tests.test_intake_plan import setup
from tests.test_service_registry import contract
from runtime.intake_plan import prepare_intake_plan, record_plan_decision
from runtime.operation_coordinator import run_operations
from runtime.human_gates import evaluate_gate
from runtime.workspace_paths import write_run_report
from tools.state_store_tools.runs import get_run, update_run_status
from tools.state_store_tools.operation_progress import progress_rows, save_progress, operation_directory
from tools.state_store_tools.service_api_uses import list_service_uses
from tools.converted_service_registry_tools.registry import open_registry, get_service


def approved(setup):
    conn, config, profile, directory, operations = setup
    prepare_intake_plan(conn, config, profile, directory, operations)
    record_plan_decision(conn, config, profile, directory, 'approved')
    profile.gate_policies = {str(number): 'automatic' for number in range(1, 5)}
    return conn, config, profile, directory


def fixtures(contract, trace, *, fail=None):
    def workflow(conn, config, profile, folder, *, execution_plan):
        packets = [packet for batch in execution_plan.batches for packet in batch.task_packets]
        assert len(packets) == 1
        key = packets[0].channel + '/' + packets[0].operation_id
        trace.append('start:' + key)
        if key.endswith('/B'):
            assert 'INTERNET/C' in {use.contract.channel + '/' + use.contract.operation_id for use in list_service_uses(conn, config.run_id)}
        if key.endswith('/A'):
            assert {'INTERNET/B', 'INTERNET/C'} <= {use.contract.channel + '/' + use.contract.operation_id for use in list_service_uses(conn, config.run_id)}
        if fail and fail(key):
            raise ValueError('controlled workflow failure')
        for number in range(1, 5):
            report = 'Same report content across operations: ' + str(number)
            write_run_report(folder, f'gate_{number}_report.txt', report)
            decision = evaluate_gate(conn, config.run_id, number, report, profile.gate_policies[str(number)], True)
            if decision != 'approved':
                update_run_status(conn, config.run_id, 'paused', f'gate_{number}_{decision}')
                return
        trace.append('finish:' + key)
        save_progress(conn, config.run_id, key, 'workflow_completed', 'operation_workflow_completed')
        update_run_status(conn, config.run_id, 'paused', 'operation_workflow_completed')
    def publication(conn, config, profile, key, folder):
        trace.append('publish:' + key)
        result = copy.deepcopy(contract)
        channel, operation = key.split('/')
        result.update(channel=channel, operation_id=operation, api_revision=operation,
                      addresses={profile.deployment_environment: {'base_url_property': operation + '_URL'}})
        result['completion']['source_run_id'] = config.run_id
        artifact = folder / 'service.jar'
        artifact.write_bytes(b'controlled packaged service')
        result['api_definition']['artifact_evidence'] = dict(root=str(folder),
            files={'service.jar': hashlib.sha256(artifact.read_bytes()).hexdigest()})
        return result
    return workflow, publication


def test_full_sequence_and_completed_resume(setup, contract):
    conn, config, profile, directory = approved(setup)
    before = conn.execute('SELECT plan_json FROM migration_plans').fetchone()[0]
    trace = []
    workflow, publication = fixtures(contract, trace)
    run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert trace == [action + ':INTERNET/' + operation for operation in ('C','B','A') for action in ('start','finish','publish')]
    assert [row['status'] for row in progress_rows(conn, config.run_id)] == ['completed'] * 3
    assert get_run(conn, config.run_id)['status'] == 'completed'
    assert conn.execute('SELECT plan_json FROM migration_plans').fetchone()[0] == before
    assert conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 1
    run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert len(trace) == 9


def test_failure_stops_callers_and_resume_keeps_completed_work(setup, contract):
    conn, config, profile, directory = approved(setup)
    trace = []
    workflow, publication = fixtures(contract, trace, fail=lambda key: key.endswith('/B'))
    with pytest.raises(ValueError, match='controlled workflow'):
        run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert 'start:INTERNET/A' not in trace
    assert progress_rows(conn, config.run_id)[0]['status'] == 'completed'
    workflow, publication = fixtures(contract, trace)
    run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert trace.count('start:INTERNET/C') == 1
    assert get_run(conn, config.run_id)['status'] == 'completed'


def test_each_operation_gate_requires_its_own_decision(setup, contract):
    from cli.gate_decisions import record_gate_decision, pending_gate_number
    conn, config, profile, directory = approved(setup)
    profile.gate_policies['2'] = 'human'
    trace = []
    workflow, publication = fixtures(contract, trace)
    run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert pending_gate_number(directory) == 2
    assert not any(item.startswith('publish:') for item in trace)
    record_gate_decision(directory, config.run_id, 2, 'approved')
    run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert progress_rows(conn, config.run_id)[0]['status'] == 'completed'
    assert get_run(conn, config.run_id)['current_phase'] == 'gate_2_pending'
    assert progress_rows(conn, config.run_id)[1]['status'] == 'paused'
    assert 'publish:INTERNET/B' not in trace
    assert 'start:INTERNET/A' not in trace


def test_publication_interruption_recovers_without_reconversion(setup, contract, monkeypatch):
    from runtime import operation_coordinator as coordinator
    conn, config, profile, directory = approved(setup)
    trace = []
    workflow, publication = fixtures(contract, trace)
    original = coordinator.publish_service
    interrupted = []
    def crash_after_commit(registry, record):
        result = original(registry, record)
        if not interrupted:
            interrupted.append(True)
            raise ValueError('interrupted after registry commit')
        return result
    monkeypatch.setattr(coordinator, 'publish_service', crash_after_commit)
    with pytest.raises(ValueError, match='interrupted'):
        run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert progress_rows(conn, config.run_id)[0]['status'] == 'publication_pending'
    run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert trace.count('start:INTERNET/C') == 1
    assert trace.count('publish:INTERNET/C') == 1
    assert get_run(conn, config.run_id)['status'] == 'completed'


def test_unapproved_plan_cannot_start(setup, contract):
    conn, config, profile, directory, operations = setup
    prepare_intake_plan(conn, config, profile, directory, operations)
    workflow, publication = fixtures(contract, [])
    run_operations(conn, config, profile, directory, workflow=lambda *args, **kwargs: pytest.fail('Started before approval'), publication_builder=publication)
    assert progress_rows(conn, config.run_id) == []

def test_publication_recovery_rejects_changed_artifact(setup, contract, monkeypatch):
    from runtime import operation_coordinator as coordinator
    conn, config, profile, directory = approved(setup)
    trace = []
    workflow, publication = fixtures(contract, trace)
    original = coordinator.publish_service
    monkeypatch.setattr(coordinator, 'publish_service', lambda *args: (_ for _ in ()).throw(ValueError('registry unavailable')))
    with pytest.raises(ValueError, match='registry unavailable'):
        run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    artifact = operation_directory(directory, 'INTERNET/C') / 'service.jar'
    artifact.write_bytes(b'changed after validation')
    monkeypatch.setattr(coordinator, 'publish_service', original)
    with pytest.raises(ValueError, match='artifacts changed'):
        run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    assert trace.count('start:INTERNET/C') == 1
    assert 'start:INTERNET/B' not in trace


def test_cli_status_shows_current_operation_and_uses_its_reports(setup, contract, monkeypatch, capsys):
    from cli.main import main
    from cli.workflow_progress import display_workflow_progress
    conn, config, profile, directory = approved(setup)
    profile.gate_policies['2'] = 'human'
    workflow, publication = fixtures(contract, [])
    run_operations(conn, config, profile, directory, workflow=workflow, publication_builder=publication)
    monkeypatch.setattr('cli.main.load_configuration', lambda path: profile)
    monkeypatch.setattr('cli.main.complete_run_selection', lambda *args: None)
    assert main(['status', '--config', 'saved.yaml', '--run-id', config.run_id]) == 0
    output = capsys.readouterr().out
    assert 'INTERNET/C' in output and 'gate_2_pending' in output
    display_workflow_progress(directory)
    output = capsys.readouterr().out
    assert 'Operations completed: 0/3' in output
    assert 'Current operation: INTERNET/C' in output
    assert str(operation_directory(directory, 'INTERNET/C')) in output
    assert main(['approve', '--config', 'saved.yaml', '--run-id', config.run_id, '--gate', '2']) == 0
