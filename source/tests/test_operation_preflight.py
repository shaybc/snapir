"""Offline intake dependency checks across scope and published service boundaries."""
import json
from types import SimpleNamespace
import pytest
from tests.test_operation_calls import vault
from tools.operation_call_tools.discovery import discover_operation_calls
from tools.operation_call_tools.preflight import check_dependencies, run_intake_preflight, require_preflight_passed
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.operation_calls import save_graph, plan_contracts
from tools.converted_service_registry_tools.registry import open_registry, publish_service
from tests.test_service_registry import contract


def test_direct_and_indirect_missing_paths(tmp_path):
    graph = discover_operation_calls(vault(tmp_path))
    result = check_dependencies(graph, ['INTERNET/A'], lambda key: None)
    assert {tuple(item['path']) for item in result['blockers']} >= {
        ('INTERNET/A', 'INTERNET/B'), ('INTERNET/A', 'INTERNET/B', 'INTERNET/C')}
    assert result['selected'] == ['INTERNET/A']
    assert not check_dependencies(graph, graph['operations'], lambda key: None)['blockers']


def test_published_boundary_does_not_reopen_its_dependencies(tmp_path, contract):
    graph = discover_operation_calls(vault(tmp_path))
    graph['calls'] = [call for call in graph['calls'] if call['step'] != 'AtoC']
    graph['issues'].append(dict(operation='INTERNET/B', step='bad', detail='Old source is unavailable'))
    from models.converted_service_contract import ConvertedServiceContract
    contract.update(channel='INTERNET', operation_id='B')
    saved = ConvertedServiceContract.model_validate(contract)
    looked_up = []
    def lookup(key):
        looked_up.append(key)
        return saved if key == 'INTERNET/B' else None
    result = check_dependencies(graph, ['INTERNET/A'], lookup)
    assert result['blockers'] == []
    assert looked_up == ['INTERNET/B']
    assert result['reused_services']['INTERNET/B']['api_revision'] == '1'


def test_missing_note_can_resolve_only_in_exact_channel(tmp_path, contract):
    graph_root = vault(tmp_path)
    (graph_root / 'operations/C.md').unlink()
    graph = discover_operation_calls(graph_root)
    assert any(issue.get('callee') == 'INTERNET/C' for issue in graph['issues'])
    from models.converted_service_contract import ConvertedServiceContract
    contract.update(channel='INTERNET', operation_id='C')
    saved = ConvertedServiceContract.model_validate(contract)
    result = check_dependencies(graph, ['INTERNET/A', 'INTERNET/B'], lambda key: saved if key == 'INTERNET/C' else None)
    assert not result['blockers']
    blocked = check_dependencies(graph, ['INTERNET/A', 'INTERNET/B'], lambda key: None)
    assert any(item['path'][-1] == 'INTERNET/C' for item in blocked['blockers'])


def test_cycle_has_complete_path_and_evidence(tmp_path):
    graph = discover_operation_calls(vault(tmp_path))
    graph['calls'].append(dict(caller='INTERNET/C', callee='INTERNET/A', step='CtoA', note='evidence.md'))
    result = check_dependencies(graph, graph['operations'], lambda key: None)
    cycles = [item['path'] for item in result['blockers'] if item['kind'] == 'cycle']
    assert cycles
    assert all(path[0] == path[-1] for path in cycles)
    edges = {(call['caller'], call['callee']) for call in graph['calls']}
    assert all((a, b) in edges for path in cycles for a, b in zip(path, path[1:]))
    assert any(call['step'] == 'CtoA' for call in result['call_evidence'])


def test_unrelated_issues_do_not_block_selected_scope(tmp_path):
    graph = discover_operation_calls(vault(tmp_path))
    graph['issues'].append(dict(operation='INTERNET/A', step='broken', detail='missing linked note'))
    assert not check_dependencies(graph, ['INTERNET/C'], lambda key: None)['blockers']
    assert check_dependencies(graph, ['INTERNET/A'], lambda key: None)['blockers']


def test_intake_saves_reports_and_planning_cannot_bypass_blocker(tmp_path, contract, monkeypatch):
    root = tmp_path / 'vault'
    root.mkdir()
    graph = discover_operation_calls(vault(root))
    conn = get_connection(str(tmp_path / 'run.db'))
    conn.execute('CREATE TABLE operations(run_id TEXT,channel TEXT,operation_id TEXT)')
    conn.execute("INSERT INTO operations VALUES ('run','INTERNET','B')")
    save_graph(conn, 'run', graph)
    plan_contracts(conn, 'run', graph, root)
    conn.commit()
    profile = SimpleNamespace(source_workspace_id='bank', source_root=str(tmp_path),
                              service_registry_path=str(tmp_path / 'registry.db'), conversion_strategy='behavior_units')
    config = SimpleNamespace(run_id='run')
    try:
        result = run_intake_preflight(conn, config, profile, tmp_path)
        assert result['blockers']
        assert json.loads((tmp_path / 'reports/1_intake_and_legacy_analysis/dependency_preflight.json').read_text()) == result
        from runtime.planning import prepare_plan
        monkeypatch.setattr('runtime.planning.AdkExecutor', lambda *args: pytest.fail('Model must not run'))
        with pytest.raises(ValueError, match='preflight is blocked'):
            prepare_plan(conn, config, profile, [dict(operation_id='B', channel='INTERNET')])
        contract.update(channel='INTERNET', operation_id='C')
        registry = open_registry(profile.service_registry_path)
        try:
            publish_service(registry, contract)
        finally:
            registry.close()
        result = run_intake_preflight(conn, config, profile, tmp_path)
        assert not result['blockers']
        assert 'INTERNET/C' in result['reused_services']
        require_preflight_passed(conn, 'run')
        assert 'Reuse published service' in (tmp_path / 'reports/1_intake_and_legacy_analysis/dependency_preflight.md').read_text()
    finally:
        conn.close()


def test_preexisting_run_without_preflight_retains_compatibility(tmp_path):
    conn = get_connection(str(tmp_path / 'old.db'))
    try:
        require_preflight_passed(conn, 'old')
    finally:
        conn.close()

def test_intake_runner_stops_before_planning_and_keeps_full_inventory(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from models.pipeline_configuration import PipelineConfiguration
    from runtime import pipeline_runner as runner
    from tools.state_store_tools.channel_operations import upsert_operation
    from tools.state_store_tools.runs import get_run
    root = tmp_path / 'vault-fixture'
    root.mkdir()
    graph = discover_operation_calls(vault(root))
    dummy = SimpleNamespace(issues=[], model_dump_json=lambda **kwargs: '{}')
    inventory = SimpleNamespace(java_dependencies=dummy, model_dump_json=lambda **kwargs: '{}')
    monkeypatch.setattr(runner, 'java_scope', lambda profile: nullcontext())
    monkeypatch.setattr(runner, 'intake_model_warning', lambda profile: None)
    monkeypatch.setattr(runner, 'discover_java_sources', lambda *args: dummy)
    monkeypatch.setattr(runner, 'discover_java_classpath', lambda *args: dummy)
    monkeypatch.setattr('tools.component_inventory_tools.build_component_inventory', lambda *args: inventory)
    monkeypatch.setattr('tools.state_store_tools.component_inventory.persist_component_inventory', lambda *args: None)
    monkeypatch.setattr('tools.state_store_tools.component_inventory.get_implementation_usage', lambda *args: [])
    monkeypatch.setattr('tools.state_store_tools.component_inventory.get_configured_component_usage', lambda *args: [])
    monkeypatch.setattr('tools.component_inventory_tools.service_inventory.service_inventory', lambda *args: [])
    commands = []
    monkeypatch.setattr(runner, 'run_java', lambda command, **kwargs: commands.append(command) or
                        SimpleNamespace(stdout='', stderr='', returncode=0))
    def import_fixture(conn, config):
        save_graph(conn, config.run_id, graph)
        plan_contracts(conn, config.run_id, graph, root)
        upsert_operation(conn, operation_id='B', channel='INTERNET', run_id=config.run_id, xml_file_path='B.xml')
        conn.commit()
        return {'paused': False}
    monkeypatch.setattr(runner, 'run_legacy_composer_analysis', import_fixture)
    monkeypatch.setattr(runner, 'build_all_context_hierarchies', lambda *args: pytest.fail('Reached planning preparation'))
    profile = PipelineConfiguration(source_root=str(tmp_path), mapper_jar='unused.jar',
        output_root=str(tmp_path / 'runs'), channels=['INTERNET'], include_operations=['B'],
        source_workspace_id='bank', service_registry_path=str(tmp_path / 'registry.db'),
        conversion_strategy='behavior_units', model_provider='mock')
    directory = runner.run_pipeline(profile, 'blocked-run')
    assert '--channel' not in commands[0]
    conn = get_connection(str(directory / 'state/migration.db'))
    try:
        run = get_run(conn, 'blocked-run')
        assert run['current_phase'] == 'dependency_preflight_blocked'
        assert run['status'] == 'paused_awaiting_operator'
    finally:
        conn.close()


def test_does_not_guess_another_channel(tmp_path):
    root = vault(tmp_path)
    path = root / 'operations/C.md'
    path.write_text(path.read_text().replace('channel: INTERNET', 'channel: IVR'))
    result = check_dependencies(discover_operation_calls(root), ['INTERNET/B'], lambda key: None)
    assert result['blockers'][0]['path'] == ['INTERNET/B', 'INTERNET/C']


def test_long_chain_has_no_recursion_limit():
    graph = dict(operations={f'WEB/{i}': {} for i in range(1200)}, issues=[], calls=[
        dict(caller=f'WEB/{i}', callee=f'WEB/{i-1}', step=str(i)) for i in range(1, 1200)])
    assert not check_dependencies(graph, graph['operations'], lambda key: None)['blockers']

def test_included_operation_requires_mapped_format_evidence(tmp_path):
    root = tmp_path / 'vault'
    root.mkdir()
    graph = discover_operation_calls(vault(root))
    (root / 'formats/F.md').unlink()
    conn = get_connection(str(tmp_path / 'run.db'))
    try:
        conn.execute('CREATE TABLE operations(run_id TEXT,channel TEXT,operation_id TEXT)')
        conn.execute("INSERT INTO operations VALUES ('run','INTERNET','C')")
        save_graph(conn, 'run', graph)
        plan_contracts(conn, 'run', graph, root)
        conn.commit()
        profile = SimpleNamespace(source_workspace_id='bank', source_root=str(tmp_path),
                                  service_registry_path=str(tmp_path / 'registry.db'))
        result = run_intake_preflight(conn, SimpleNamespace(run_id='run'), profile, tmp_path)
        assert result['blockers'][0]['kind'] == 'missing_evidence'
        assert 'format evidence' in result['blockers'][0]['detail']
    finally:
        conn.close()
