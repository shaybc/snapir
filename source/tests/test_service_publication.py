"""Check full service-publication evidence and pinned native call adaptation offline."""

import hashlib
import json
from pathlib import Path
import pytest
from tests.test_intake_plan import setup
from tests.test_service_registry import contract
from runtime.service_publication import prepare_publication
from runtime.human_gates import operation_gate_scope, record_decision
from runtime.workspace_paths import write_run_report
from tools.state_store_tools.runs import update_run_status
from tools.state_store_tools.operation_calls import load_graph
from tools.state_store_tools.service_api_uses import record_service_use
from tools.operation_call_tools.published_calls import resolve_published_calls, verify_pinned_call


def publication_evidence(setup):
    conn, config, profile, directory, operations = setup
    output = directory / 'services/INTERNET/C/target/service.jar'
    output.parent.mkdir(parents=True)
    output.write_bytes(b'controlled package artifact')
    relative = str(output.relative_to(directory)).replace('\\', '/')
    manifest = dict(production_ready=True, blockers=[], operations=[dict(channel='INTERNET', operation_id='C', blockers=[],
        files={relative: hashlib.sha256(output.read_bytes()).hexdigest()})])
    write_run_report(directory, 'delivery_manifest.json', json.dumps(manifest))
    write_run_report(directory, 'final_report.md', 'Validated delivery report')
    report_folder = directory / 'reports/2_migration_planning/gate_1'
    report_folder.mkdir(parents=True, exist_ok=True)
    (report_folder / 'manifest.json').write_text('[]')
    write_run_report(directory, 'gate_1_report.md', '# Operation C gate one')
    from runtime.gate_one_reports import read_gate_one_reports
    with operation_gate_scope('INTERNET/C'):
        record_decision(conn, config.run_id, 1, read_gate_one_reports(directory), 'approved')
        for number in (2,3,4):
            report = 'Validated operation report ' + str(number)
            write_run_report(directory, f'gate_{number}_report.txt', report)
            record_decision(conn, config.run_id, number, report, 'approved')
    conn.execute('CREATE TABLE service_generation_checkpoints(run_id TEXT,operation_id TEXT,channel TEXT,validation_json TEXT)')
    validation = dict(build_passed=True, package_passed=True, ibm_guard_passed=True, test_status='passed',
                      xml_compatibility='passed', behavioral_equivalence='passed', legacy_trace_comparison='passed')
    conn.execute('INSERT INTO service_generation_checkpoints VALUES (?,?,?,?)',
                 (config.run_id, 'C', 'INTERNET', json.dumps(validation)))
    conn.commit()
    update_run_status(conn, config.run_id, 'paused', 'operation_workflow_completed')
    return conn, config, profile, directory, output


def test_publication_has_full_api_and_stable_revision(setup):
    conn, config, profile, directory, output = publication_evidence(setup)
    with operation_gate_scope('INTERNET/C'):
        result = prepare_publication(conn, config, profile, 'INTERNET/C', directory)
        assert result == prepare_publication(conn, config, profile, 'INTERNET/C', directory)
    assert result['status'] == 'converted'
    assert result['request_contract']['markdown']
    assert result['response_contract']['markdown']
    assert result['error_contract']['markdown']
    assert result['addresses'][profile.deployment_environment]['base_url_property']
    assert result['completion']['gates_approved'] is True


@pytest.mark.parametrize('failure', ['package', 'tests', 'gate', 'artifact', 'unfinished'])
def test_incomplete_service_cannot_prepare_publication(setup, failure):
    conn, config, profile, directory, output = publication_evidence(setup)
    if failure in {'package','tests'}:
        row = conn.execute('SELECT validation_json FROM service_generation_checkpoints').fetchone()
        validation = json.loads(row[0])
        validation['package_passed' if failure == 'package' else 'test_status'] = False
        conn.execute('UPDATE service_generation_checkpoints SET validation_json=?', (json.dumps(validation),))
        conn.commit()
    elif failure == 'artifact':
        output.write_bytes(b'changed package')
    elif failure == 'unfinished':
        update_run_status(conn, config.run_id, 'paused', 'service_generation_pending')
    else:
        with operation_gate_scope('INTERNET/C'):
            record_decision(conn, config.run_id, 4, 'Validated operation report 4', 'rejected')
    with operation_gate_scope('INTERNET/C'), pytest.raises(ValueError):
        prepare_publication(conn, config, profile, 'INTERNET/C', directory)


def test_pinned_contract_call_uses_saved_wire_types_without_callee_source(setup, contract):
    conn, config, profile, directory, operations = setup
    contract.update(channel='INTERNET', operation_id='C', addresses={profile.deployment_environment: {'base_url_property':'C_URL'}})
    record_service_use(conn, config.run_id, contract, profile.deployment_environment)
    graph = load_graph(conn, config.run_id)
    graph['issues'].append(dict(operation='INTERNET/C', step='old', detail='C internal source unavailable'))
    calls, issues = resolve_published_calls(conn, config.run_id, 'INTERNET/B', ['BtoC'], graph, profile)
    assert not issues and len(calls) == 1
    assert calls[0]['service_contract']['formats']['csRequestFormat'] == contract['request_contract']
    assert calls[0]['service_contract']['base_url_property'] == 'C_URL'
    verify_pinned_call(conn, config.run_id, calls[0])
    calls[0]['service_contract']['path'] = '/invented'
    with pytest.raises(ValueError, match='binding changed'):
        verify_pinned_call(conn, config.run_id, calls[0])


def test_missing_published_binding_blocks_caller(setup):
    conn, config, profile, directory, operations = setup
    calls, issues = resolve_published_calls(conn, config.run_id, 'INTERNET/B', ['BtoC'], load_graph(conn, config.run_id), profile)
    assert not calls and issues
    assert 'publish' in issues[0].detail
