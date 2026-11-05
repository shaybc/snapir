"""Verify source-backed assembly values without exposing secrets or starting a service."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.operation_assembly.values import prepare_operation_values
from runtime.service_generation.composer_database_settings import credential_free_url, discover_database_settings
from runtime.service_generation.deployment_configuration import read_deployment, write_deployment
from runtime.workspace_paths import run_report_path
from tests.test_service_connector_discovery import workspace, resolve


def configured(tmp_path):
    root, _, _, definitions = workspace(tmp_path)
    records = [item.model_dump() for item in resolve(root, 'getService("regular"); getService("transaction");')]
    project = tmp_path / 'generated/INTERNET/Op'
    project.mkdir(parents=True)
    conn = sqlite3.connect(':memory:')
    config = SimpleNamespace(source_root=str(root), run_id='fixture', output_root=str(tmp_path/'generated'))
    record = dict(project=str(project), channel='INTERNET', operation_id='Op', service_connections=records)
    return root, definitions, records, project, conn, config, record


def test_effective_pool_populates_only_nonsecret_settings_during_assembly(tmp_path):
    root, definitions, records, project, conn, config, record = configured(tmp_path)
    # Unloaded files must never supply runtime settings.
    (definitions / 'unused.xml').write_text('<XML><column id="pool" JDBCDriver="wrong.Driver" databaseURL="jdbc:wrong:host"/></XML>')
    found = discover_database_settings(root, 'INTERNET', records)
    assert found['jdbcUrl'] == 'jdbc:oracle:thin:privateEndpoint'
    assert found['driverClass'] == 'example.Driver' and not found['issues']
    assert 'privateEndpoint' not in json.dumps(records)  # Existing AI sanitization is retained.
    result = prepare_operation_values(conn, config, tmp_path, record)
    spec = read_deployment(project / 'values.yaml')
    assert result['filled_fields'] == ['jdbcUrl', 'driverClass']
    assert spec.databases['default'].jdbcUrl == found['jdbcUrl']
    assert spec.databases['default'].driverClass == found['driverClass']
    assert spec.databases['default'].credentialsSecret.name == 'internet-op-database'
    exported = (project / 'values.yaml').read_text() + run_report_path(tmp_path, 'operation_values_results.json').read_text()
    assert 'privatePassword' not in exported and 'privateUser' not in exported
    assert not (tmp_path / 'services').exists() and not (tmp_path / 'shared-runtime').exists()


@pytest.mark.parametrize('url', [
    'jdbc:oracle:thin:user/password@host', 'jdbc:postgresql://user:password@host/db',
    'jdbc:postgresql://host/db?user=secret', 'jdbc:sqlserver://host;password=secret',
    'jdbc:postgresql://host/db?accessToken=secret', 'jdbc:postgresql://host/db?pwd=secret',
    'jdbc:postgresql://host/db?password%3Dsecret', 'jdbc:postgresql://host/db?password%253Dsecret',
    'jdbc:db2://host/db:uid=secret', 'jdbc:db2://host/db:User ID=secret', 'jdbc:custom:host;pass=secret',
    'jdbc:postgresql://${HOST}/db', 'jdbc:postgresql://%HOST%/db',
])
def test_credential_bearing_or_unresolved_urls_are_not_exported(tmp_path, url):
    root, definitions, records, project, conn, config, record = configured(tmp_path)
    path = definitions / 'connectors.tmp'
    path.write_text(path.read_text().replace('jdbc:oracle:thin:privateEndpoint', url))
    assert not credential_free_url(url)
    result = prepare_operation_values(conn, config, tmp_path, record)
    spec = read_deployment(project / 'values.yaml')
    assert spec.databases['default'].jdbcUrl == ''
    assert spec.databases['default'].driverClass == 'example.Driver'
    assert result['issues'] and url not in json.dumps(result)
    assert url not in (project / 'values.yaml').read_text()


@pytest.mark.parametrize('url', ['jdbc:oracle:thin:@//host:1521/service',
    'jdbc:postgresql://host:5432/db?sslmode=require', 'jdbc:sqlserver://host:1433;databaseName=db;encrypt=true'])
def test_supported_credential_free_urls(url):
    assert credential_free_url(url)


def test_user_settings_secret_references_comments_and_crlf_are_preserved(tmp_path):
    root, definitions, records, project, conn, config, record = configured(tmp_path)
    prepare_operation_values(conn, config, tmp_path, record)
    path = project / 'values.yaml'
    spec = read_deployment(path)
    spec.databases['default'].jdbcUrl = 'jdbc:custom:chosen'
    spec.databases['default'].driverClass = ''
    spec.databases['default'].credentialsSecret.name = 'user-selected-secret'
    spec.operation.initialization = {'ExactCase': 'retained'}
    write_deployment(path, spec)
    before = ('# retain this comment\n' + path.read_text(encoding='utf-8')).replace('\n', '\r\n').encode('utf-8')
    path.write_bytes(before)
    result = prepare_operation_values(conn, config, tmp_path, record)
    assert result['filled_fields'] == ['driverClass'] and result['preserved_fields'] == ['jdbcUrl']
    assert path.read_bytes() == before.replace(b"driverClass: ''", b'driverClass: "example.Driver"')
    before = path.read_bytes()
    prepare_operation_values(conn, config, tmp_path, record)
    assert path.read_bytes() == before


def test_absent_pool_ambiguous_pool_and_stale_evidence_are_unresolved(tmp_path):
    root, definitions, records, project, conn, config, record = configured(tmp_path)
    assert discover_database_settings(root, 'INTERNET', [])['issues']
    other = dict(records[0], connector_id='other')
    ambiguous = discover_database_settings(root, 'INTERNET', records + [other])
    assert ambiguous['issues'] and ambiguous['jdbcUrl'] == '' and ambiguous['driverClass'] == ''
    path = definitions / 'services.tmp'
    original = path.read_text()
    path.write_text(original.replace('poolName="pool"', 'poolName="other"'))
    assert 'binding changed' in discover_database_settings(root, 'INTERNET', records)['issues'][0]
    path.write_text(original)
    stale = [dict(records[0], driver_class='stale.Driver')]
    assert 'driver changed' in discover_database_settings(root, 'INTERNET', stale)['issues'][0]
    assert discover_database_settings(root, 'OTHER', records)['jdbcUrl'] == ''


def test_caller_supplied_connection_leaves_blanks_and_existing_yaml_unchanged(tmp_path):
    _, _, _, project, conn, config, record = configured(tmp_path)
    record['service_connections'] = []
    record['service_api'] = dict(method_signatures=['public String execute(String xml, java.sql.Connection connection)'])
    result = prepare_operation_values(conn, config, tmp_path, record)
    assert 'caller-supplied' in result['issues'][0]
    path = project / 'values.yaml'
    before = path.read_bytes()
    prepare_operation_values(conn, config, tmp_path, record)
    assert path.read_bytes() == before
    assert read_deployment(path).databases['default'].jdbcUrl == ''


def test_persisted_operation_bindings_are_used_without_database_mutation(tmp_path):
    _, _, records, project, conn, config, record = configured(tmp_path)
    conn.execute('CREATE TABLE service_connection_evidence (run_id, consumer, record_json)')
    conn.execute('INSERT INTO service_connection_evidence VALUES (?, ?, ?)',
        (config.run_id, 'INTERNET/Op', json.dumps(records[0])))
    record.pop('service_connections')
    before = list(conn.iterdump())
    prepare_operation_values(conn, config, tmp_path, record)
    assert list(conn.iterdump()) == before
    assert read_deployment(project / 'values.yaml').databases['default'].driverClass == 'example.Driver'


def test_legacy_assembly_creates_values_before_review_and_reuses_without_generation(tmp_path):
    from tests.runtime.test_operation_assembly import assembly_setup, run, implement
    setup, plans, factory, gate = assembly_setup(tmp_path)
    assert run(tmp_path, setup, plans, factory, gate, implement) == 'operation_review_pending'
    path = Path(setup[1].output_root) / 'INTERNET/Op/values.yaml'
    assert path.exists() and not (tmp_path / 'services').exists()
    before = path.read_bytes()
    assert run(tmp_path, setup, plans, factory, gate,
        lambda *args: pytest.fail('Reused assembly called model')) == 'operation_review_pending'
    assert path.read_bytes() == before


def test_native_assembly_creates_values_before_gate_three(tmp_path, monkeypatch):
    from tests.runtime.test_behavior_pipeline import setup, invoke, Model
    # This unrelated standalone fixture writer needs tables not created by the unit fixture.
    monkeypatch.setattr('runtime.behavior_conversion.standalone_sample.write_operation_sample', lambda *args, **kwargs: None)
    monkeypatch.setattr('runtime.service_generation.run_service_generation', lambda *args, **kwargs: pytest.fail('Packaging before Gate 3'))
    data = setup(tmp_path)
    data[2].gate_policies['3'] = 'human'
    invoke(tmp_path, data, Model())
    assert data[0].execute('SELECT current_phase FROM runs').fetchone()[0] == 'gate_3_pending'
    assert (Path(data[1].output_root) / 'WEB/Transfer/values.yaml').exists()
    assert not (tmp_path / 'services').exists()
