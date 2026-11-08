"""Verify automatic source closure and registry boundaries without enabling generation."""
from types import SimpleNamespace

import pytest

from test_scoped_closure import workspace
from test_scoped_vault_identity import scoped_mapper, invoke_mapper
from test_scoped_workflow import settings, prepare
from test_service_registry import contract
from models.java_source_index import JavaSourceIndex
from tools.composer_mapper_tools.vault_importer import import_vault
from tools.conversion_tools.dependency_planning.required_scope import required_scope
from tools.conversion_tools.scoped_workflow.source_project import scoped_source_project
from tools.converted_service_registry_tools.registry import open_registry, publish_service
from tools.state_store_tools.db import get_connection, create_all_tables


def selected_workspace(tmp_path, mapper, change=None):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    workspace(root)
    if change:
        change(root)
    result = invoke_mapper(mapper, root, vault)
    assert result.returncode == 0, result.stderr
    conn = get_connection(':memory:')
    create_all_tables(conn)
    config, profile = settings(root, vault)
    config.run_mode = SimpleNamespace(value='selected_channels')
    config.target_channels = ['SME']
    config.include_operations = ['Caller']
    import_vault(conn, str(vault), config, progress=lambda message: None)
    profile.scoped_java_project = None
    profile.model_provider = 'mock'
    return conn, config, profile, root


def test_selected_root_prepares_imported_operation_and_all_components(tmp_path, scoped_mapper):
    conn, config, profile, root = selected_workspace(tmp_path, scoped_mapper)
    before = list(conn.execute('SELECT operation_id,channel,selected FROM scoped_operation_contexts ORDER BY 1,2'))
    report = prepare(conn, config, profile)
    assert report['requested_operations'] == ['SME/Caller']
    assert report['required_operations'] == ['SME/Caller', 'SME/Flow']
    assert report['dependency_plan']['order'] == ['SME/Flow', 'SME/Caller']
    assert all(item['status'] == 'prepared' for item in report['operations'].values()), report
    assert set(report['dependency_plan']['source_projects'].values()) == {'.'}
    components = report['dependency_plan']['components'].values()
    assert any(item['logical_id'] == 'example.Work' and item['source'] == 'source' for item in components)
    assert any(item['logical_id'] == 'example.Field' for item in components)
    assert list(conn.execute('SELECT operation_id,channel,selected FROM scoped_operation_contexts ORDER BY 1,2')) == before
    assert config.target_channels == ['SME'] and config.include_operations == ['Caller']
    assert profile.scoped_java_project is None and profile.scoped_java_projects == {}
    assert not report['conversion_enabled'] and profile.scoped_native_mode == 'prepare'
    again = prepare(conn, config, profile)
    assert again['reused_contexts'] == ['SME/Caller', 'SME/Flow']
    assert again['operations'] == report['operations']
    (root / 'src/example/Work.java').write_text('package example; public class Work { int changed; }')
    from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale
    with pytest.raises(ScopedCheckpointStale):
        prepare(conn, config, profile)
    conn.close()


def test_published_dependency_is_pinned_automatically_and_prunes_source(tmp_path, scoped_mapper, contract):
    conn, config, profile, root = selected_workspace(tmp_path, scoped_mapper)
    profile.source_workspace_id = 'bank'
    contract.update(channel='SME', operation_id='Flow')
    registry_path = tmp_path / 'shared/operations/registry.db'
    profile.service_registry_path = str(registry_path)
    with open_registry(registry_path) as registry:
        publish_service(registry, contract)
    (root / 'src/example/Work.java').unlink()
    report = prepare(conn, config, profile)
    assert set(report['operations']) == {'SME/Caller'}
    assert report['operations']['SME/Caller']['status'] == 'prepared', report
    assert report['operations']['SME/Caller']['calls'][0]['service_contract']['published_api']
    assert report['dependency_plan']['reused_services']['SME/Flow']['api_revision'] == '1'
    assert conn.execute('SELECT count(*) FROM service_api_uses').fetchone()[0] == 1
    contract['api_revision'] = '2'
    with open_registry(registry_path) as registry:
        publish_service(registry, contract)
    again = prepare(conn, config, profile)
    assert again['dependency_plan']['reused_services']['SME/Flow']['api_revision'] == '1'
    assert again['operations'] == report['operations']
    conn.close()


def test_cross_channel_dependencies_and_explicit_exclusion():
    graph = dict(operations={'WEB/A': {}, 'XML/B': {}, 'XML/C': {}}, issues=[], calls=[
        dict(caller='WEB/A', callee='XML/B'), dict(caller='XML/B', callee='XML/C')])
    plan = required_scope(graph, ['WEB/A'])
    assert plan.order == ['XML/C', 'XML/B', 'WEB/A']
    assert plan.operation_paths['XML/C'] == ['WEB/A', 'XML/B', 'XML/C']
    assert not plan.blockers
    blocked = required_scope(graph, ['WEB/A'], excluded=['B'])
    assert blocked.blockers[0]['kind'] == 'excluded_dependency'
    reused = required_scope(graph, ['WEB/A'], lambda key: {'api_revision': '1'} if key == 'XML/B' else None, excluded=['B'])
    assert reused.source_operations == ['WEB/A'] and not reused.blockers


def test_ambiguous_target_is_not_converted_by_name():
    graph = dict(operations={'WEB/A': {}, 'WEB/B': {}}, calls=[], issues=[
        dict(operation='WEB/A', callee='WEB/B', detail='Ambiguous target source')])
    plan = required_scope(graph, ['WEB/A'])
    assert plan.blockers[0]['kind'] == 'unresolved_target'
    assert plan.source_operations == ['WEB/A']


@pytest.mark.parametrize('published', [False, True])
def test_missing_callee_xml_requires_an_exact_published_api(tmp_path, scoped_mapper, contract, published):
    from xml.etree import ElementTree
    def remove_operation(root):
        path = root / 'Channel/XML/Flows.xml'
        tree = ElementTree.parse(path)
        tree.getroot().remove(tree.getroot().find('CCDSEServerOperation'))
        tree.write(path, encoding='utf-8')
    conn, config, profile, root = selected_workspace(tmp_path, scoped_mapper, change=remove_operation)
    profile.source_workspace_id = 'bank'
    profile.service_registry_path = str(tmp_path / 'shared/operations/registry.db')
    if published:
        contract.update(channel='SME', operation_id='Flow')
        with open_registry(profile.service_registry_path) as registry:
            publish_service(registry, contract)
    (root / 'src/example/Work.java').unlink()
    report = prepare(conn, config, profile)
    assert set(report['operations']) == {'SME/Caller'}
    caller = report['operations']['SME/Caller']
    assert caller['status'] == ('prepared' if published else 'blocked'), report
    if published:
        assert caller['calls'][0]['service_contract']['published_api']
        assert not report['dependency_plan']['blockers']
    else:
        assert report['dependency_plan']['blockers']
    conn.close()


def test_registry_owner_inference_uses_declared_project_not_imported_class(tmp_path):
    for folder, name, channel in [('internet-src', 'Consumer', 'WEB'), ('xml-src', 'Imported', 'XML')]:
        project = tmp_path / folder
        (project / 'Channel' / channel).mkdir(parents=True)
        (project / '.project').write_text('<projectDescription><name>' + name + '</name></projectDescription>')
        (project / 'Channel' / channel / 'dse.ini').write_text('<dse.ini/>')
        (project / 'src').mkdir()
    index = JavaSourceIndex(workspace_root=str(tmp_path), source_roots={
        'Consumer': [str(tmp_path / 'internet-src/src')], 'Imported': [str(tmp_path / 'xml-src/src')]})
    profile = SimpleNamespace(source_root=str(tmp_path), scoped_java_projects={}, scoped_java_project=None)
    assert scoped_source_project(profile, 'WEB', source_index=index) == 'Consumer'
    assert scoped_source_project(profile, 'XML', source_index=index) == 'Imported'
    duplicate = tmp_path / 'xml-src/Channel/WEB'
    duplicate.mkdir()
    (duplicate / 'dse.ini').write_text('<dse.ini/>')
    assert scoped_source_project(profile, 'WEB', source_index=index) is None
    profile.scoped_java_projects = {'WEB': 'Consumer'}
    assert scoped_source_project(profile, 'WEB', source_index=index) == 'Consumer'
