"""Offline acceptance of intake plans, content-bound approval and CLI handoff."""

import json
from pathlib import Path

import pytest
from models.pipeline_configuration import PipelineConfiguration
from runtime.intake_plan import prepare_intake_plan, resume_intake_plan, record_plan_decision, dependency_plan_context, validate_dependency_order
from runtime.workspace_paths import run_database_path, run_profile_path, run_report_path
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.runs import get_run
from tools.workspace_intake_tools.run_factory import persist_run_config
from tools.state_store_tools.operation_calls import save_graph, plan_contracts
from tools.state_store_tools.channel_operations import upsert_operation
from tools.operation_call_tools.preflight import run_intake_preflight
from tools.operation_call_tools.discovery import discover_operation_calls
from tests.test_operation_calls import vault
from tests.test_migration_planning import run_config
from tests.test_service_registry import contract


@pytest.fixture
def setup(tmp_path):
    directory = tmp_path / 'run-1'
    (directory / 'state').mkdir(parents=True)
    root = directory / 'vault'
    root.mkdir()
    graph = discover_operation_calls(vault(root))
    config = run_config().model_copy(update=dict(vault_root=str(root), db_path=str(run_database_path(directory))))
    profile = PipelineConfiguration(source_root=str(tmp_path), mapper_jar='unused.jar',
        source_workspace_id='bank', service_registry_path=str(tmp_path / 'registry.db'),
        output_root=str(tmp_path), conversion_strategy='behavior_units', model_provider='mock', deployment_environment='test')
    conn = get_connection(str(run_database_path(directory)))
    create_all_tables(conn)
    persist_run_config(conn, config, directory)
    run_profile_path(directory).write_text(profile.model_dump_json(), encoding='utf-8')
    for operation in ('A', 'B', 'C'):
        upsert_operation(conn, operation_id=operation, channel='INTERNET', run_id=config.run_id, xml_file_path=operation + '.xml')
    save_graph(conn, config.run_id, graph)
    plan_contracts(conn, config.run_id, graph, root)
    conn.commit()
    run_intake_preflight(conn, config, profile, directory)
    operations = [dict(operation_id=operation, channel='INTERNET') for operation in ('A', 'B', 'C')]
    yield conn, config, profile, directory, operations
    conn.close()


def test_plan_order_waves_and_human_approval(setup):
    conn, config, profile, directory, operations = setup
    plan = prepare_intake_plan(conn, config, profile, directory, operations)
    assert [packet.operation_id for batch in plan.batches for packet in batch.task_packets] == ['C', 'B', 'A']
    assert get_run(conn, config.run_id)['current_phase'] == 'conversion_plan_pending'
    snapshot = json.loads(run_report_path(directory, 'conversion_plan.json').read_text())
    assert [item['wave'] for item in snapshot['dependency_context']['operations']] == [1, 2, 3]
    report = run_report_path(directory, 'conversion_plan.md').read_text()
    assert 'INTERNET/B, INTERNET/C' in report
    assert resume_intake_plan(conn, config, profile, directory) == 'pending'
    record_plan_decision(conn, config, profile, directory, 'approved')
    assert resume_intake_plan(conn, config, profile, directory) == 'approved'
    assert get_run(conn, config.run_id)['current_phase'] == 'conversion_plan_approved'
    assert conn.execute('SELECT DISTINCT gate_number FROM runtime_gate_decisions').fetchall()[0][0] == 0


@pytest.mark.parametrize('policy', ['automatic', 'skip'])
def test_saved_automatic_policy(setup, policy):
    conn, config, profile, directory, operations = setup
    profile.plan_approval_policy = policy
    prepare_intake_plan(conn, config, profile, directory, operations)
    row = conn.execute('SELECT policy,decision FROM runtime_gate_decisions WHERE gate_number=0').fetchone()
    assert tuple(row) == (policy, 'approved')
    assert profile.gate_policies.keys() == {'1','2','3','4'}


def test_dependency_order_cannot_be_overridden_by_pilot(setup):
    conn, config, profile, directory, operations = setup
    plan = prepare_intake_plan(conn, config, profile, directory, operations)
    plan.batches[0].task_packets.reverse()
    assert validate_dependency_order(conn, config.run_id, plan)


@pytest.mark.parametrize('change', ['scope', 'graph', 'markdown', 'json', 'source_note', 'blocker', 'policy', 'plan'])
def test_changed_evidence_invalidates_approval(setup, change):
    conn, config, profile, directory, operations = setup
    prepare_intake_plan(conn, config, profile, directory, operations)
    record_plan_decision(conn, config, profile, directory, 'approved')
    if change == 'scope':
        conn.execute("DELETE FROM operations WHERE operation_id='A'")
    elif change == 'graph':
        graph = discover_operation_calls(config.vault_root)
        graph['calls'][0]['evidence_hash'] = 'changed'
        save_graph(conn, config.run_id, graph)
    elif change == 'markdown':
        run_report_path(directory, 'conversion_plan.md').write_text('Edited report')
    elif change == 'json':
        run_report_path(directory, 'conversion_plan.json').write_text('{}')
    elif change == 'source_note':
        path = Path(config.vault_root) / 'operations/A.md'
        path.write_text(path.read_text() + '\nChanged evidence')
    elif change == 'blocker':
        row = conn.execute('SELECT report_json FROM operation_dependency_preflights').fetchone()
        data = json.loads(row[0]); data['blockers'] = [dict(detail='missing')]
        conn.execute('UPDATE operation_dependency_preflights SET report_json=?', (json.dumps(data),))
    elif change == 'policy':
        profile.plan_approval_policy = 'automatic'
    else:
        row = conn.execute('SELECT plan_json FROM migration_plans').fetchone()
        data = json.loads(row[0]); data['batches'][0]['task_packets'][0]['generation_notes'] = ['changed']
        conn.execute('UPDATE migration_plans SET plan_json=?', (json.dumps(data),))
    conn.commit()
    with pytest.raises(ValueError):
        resume_intake_plan(conn, config, profile, directory)
    assert get_run(conn, config.run_id)['current_phase'] == 'conversion_plan_blocked'
    with pytest.raises(ValueError):
        record_plan_decision(conn, config, profile, directory, 'approved')


def test_cli_plan_decision_and_rejection(setup):
    from cli.gate_decisions import pending_gate_number, record_gate_decision
    conn, config, profile, directory, operations = setup
    prepare_intake_plan(conn, config, profile, directory, operations)
    assert pending_gate_number(directory) == 'plan'
    record_gate_decision(directory, config.run_id, 'plan', 'rejected')
    assert resume_intake_plan(conn, config, profile, directory) == 'rejected'
    record_gate_decision(directory, config.run_id, 'plan', 'approved')
    assert resume_intake_plan(conn, config, profile, directory) == 'approved'
    assert pending_gate_number(directory) is None


def test_resume_does_not_enter_batch_converter(setup, monkeypatch):
    from contextlib import nullcontext
    from runtime import checkpoints
    conn, config, profile, directory, operations = setup
    prepare_intake_plan(conn, config, profile, directory, operations)
    monkeypatch.setattr(checkpoints, 'java_scope', lambda profile: nullcontext())
    monkeypatch.setattr(checkpoints, 'run_model_diagnostics', lambda directory: nullcontext())
    monkeypatch.setattr('runtime.conversion_strategy.resume_behavior_strategy', lambda *args: pytest.fail('Entered batch converter'))
    sequential_calls = []
    monkeypatch.setattr('runtime.operation_coordinator.run_operations', lambda *args: sequential_calls.append(args[1].run_id))
    assert checkpoints.resume_pipeline(str(directory.parent), config.run_id) == directory
    assert sequential_calls == []
    record_plan_decision(conn, config, profile, directory, 'approved')
    assert checkpoints.resume_pipeline(str(directory.parent), config.run_id) == directory
    assert sequential_calls == [config.run_id]
    assert get_run(conn, config.run_id)['current_phase'] == 'conversion_plan_approved'


def test_published_boundary_in_plan_and_revision_change(setup, contract):
    from tools.converted_service_registry_tools.registry import open_registry, publish_service
    conn, config, profile, directory, operations = setup
    conn.execute("DELETE FROM operations WHERE operation_id='C'")
    conn.commit()
    contract.update(channel='INTERNET', operation_id='C')
    registry = open_registry(profile.service_registry_path)
    try:
        publish_service(registry, contract)
        run_intake_preflight(conn, config, profile, directory)
        prepare_intake_plan(conn, config, profile, directory, operations[:2])
        assert dependency_plan_context(conn, config.run_id)['order'] == ['INTERNET/B','INTERNET/A']
        assert 'revision 1' in run_report_path(directory, 'conversion_plan.md').read_text()
        record_plan_decision(conn, config, profile, directory, 'approved')
        contract['api_revision'] = '2'
        publish_service(registry, contract)
        assert resume_intake_plan(conn, config, profile, directory) == 'approved'
        run_intake_preflight(conn, config, profile, directory)
        with pytest.raises(ValueError, match='evidence changed'):
            resume_intake_plan(conn, config, profile, directory)
    finally:
        registry.close()

def test_cli_plan_approval_uses_separate_setting_and_checkpoint(setup, monkeypatch, capsys):
    from cli.main import main
    from cli.workflow_progress import checkpoint_guidance
    conn, config, profile, directory, operations = setup
    prepare_intake_plan(conn, config, profile, directory, operations)
    monkeypatch.setattr('cli.main.load_configuration', lambda path: profile)
    monkeypatch.setattr('cli.main.complete_run_selection', lambda *args: None)
    assert main(['approve', '--config', 'saved.yaml', '--run-id', config.run_id, '--gate', 'plan']) == 0
    details, action = checkpoint_guidance(directory, 'paused', 'conversion_plan_pending')
    assert details[0] == 'Conversion plan approved'
    assert 'Resume' in action
    assert conn.execute('SELECT gate_number FROM runtime_gate_decisions').fetchone()[0] == 0
