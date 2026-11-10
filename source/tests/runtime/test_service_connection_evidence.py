"""Prove per-unit propagation, grouped questions, selective reuse and driver safeguards."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from models.behavior_unit import BehaviorUnitInput, SourceEvidence
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.service_connection_evidence import attach_unit_connections
from runtime.behavior_conversion.connection_contract import attach_connections
from runtime.behavior_conversion.service_connection_freshness import verify_connection_sources
from runtime.behavior_conversion.generation import bounded_unit_evidence, generate, EvidenceSummary
from runtime.behavior_conversion.request_context import encode_request
from runtime.service_generation.connection_wiring import validate_connection_wiring
from runtime.service_connection_questions import resolve_pending_connections
from tools.state_store_tools.service_connections import pending_questions, remember, save_decision
from tools.component_inventory_tools.service_connections import resolve_service_connections
from tools.source_discovery_tools import discover_java_sources
from tools.source_discovery_tools.classpath import discover_java_classpath
from tests.test_service_connector_discovery import workspace, resolve
from tests.runtime.test_behavior_conversion import state, profile, Verifier
from tools.maven_dependency_tools.build_context import ManagedBuildContext


def setup_unit(tmp_path, kind='configured_step', service='regular'):
    root, _, _, _ = workspace(tmp_path)
    conn, config = state()
    config.source_root = str(root)
    source = 'class Step { Object execute() { return getContext().getService("' + service + '"); } }'
    unit = BehaviorUnitInput(unit_id='old', kind=kind, logical_id='dbStep', configuration_xml='<opStep id="dbStep"/>',
        sources=[SourceEvidence(identity='example.Step', content=source, content_hash=hashlib.sha256(source.encode()).hexdigest())],
        consumers=['INTERNET/Transfer'], fingerprint='original')
    closure = {'channel': 'INTERNET', 'operation_id': 'Transfer'}
    settings = profile(source_root=str(root), java_home='C:/Program Files/Java/jdk-25.0.3')
    return conn, config, settings, closure, unit


@pytest.mark.parametrize('kind', ['configured_step', 'request_unformat', 'response_format'])
def test_each_whole_unit_gets_connection_xml_source_and_known_driver_before_first_request(tmp_path, kind):
    conn, config, settings, closure, original = setup_unit(tmp_path, kind)
    unit = attach_unit_connections(conn, config, closure, original, settings)
    calls = []
    evidence = bounded_unit_evidence(conn, config, settings, unit, lambda *args: pytest.fail('Unexpected preliminary model call'))
    attach_connections(evidence, unit.service_connections)
    assert evidence['service_connections'][0]['database_type'] == 'Oracle'
    assert evidence['known_dependencies'][0]['version'] == '1.2.3'
    assert any('RegularService' in source['content'] for source in evidence['sources'])
    assert 'privatePassword' not in json.dumps(evidence)
    def model(instruction, encoded):
        request = json.loads(encoded)
        calls.append((instruction, request))
        assert 'Do not introduce another vendor' in instruction
        assert request['service_connections'][0]['database_type'] == 'Oracle'
        assert any(item['heading'] == 'Services and Connector Identification' for item in request['composer_behavior_evidence'])
        return json.dumps({'findings': ['Resolved Oracle connection']})
    generate(conn, config, settings, 'analysis', unit.unit_id, 'Analyze complete unit', evidence, EvidenceSummary, model_call=model)
    generate(conn, config, settings, 'analysis', unit.unit_id, 'Analyze complete unit with clearer wording', evidence, EvidenceSummary, model_call=model)
    assert len(calls) == 1  # Wording change reuses accepted evidence.


def test_two_services_same_pool_ask_once_and_reuse_a_verified_version_decision(tmp_path, monkeypatch):
    root, _, _, _ = workspace(tmp_path)
    jar = root / 'Project/driver.jar'
    with ZipFile(jar, 'w') as contents:
        contents.writestr('example/Driver.class', b'fixture')
    records = resolve(root, 'getService("regular"); getService("transaction");')
    conn, config = state()
    config.source_root = str(root)
    remember(conn, config.run_id, 'INTERNET/One', 'step', records[:1])
    remember(conn, config.run_id, 'INTERNET/Two', 'step', records[1:])
    questions = pending_questions(conn, config.run_id)
    assert len(questions) == 1 and len(questions[0]['consumers']) == 2
    dependency = dict(group_id='example', artifact_id='vendor-driver', version='2.0', scope='runtime',
                      reason='Verified user-selected version', required_classes=['example.Driver'])
    question = questions[0]
    save_decision(conn, config.run_id, question['connection_id'], question['fingerprint'], {'driver_dependency': dependency})
    from runtime.behavior_conversion.service_connection_evidence import connection_evidence
    selected, _, _ = connection_evidence(conn, config, 'INTERNET', 'One/step', {'Step': 'getService("regular");'}, '<opStep/>')
    assert not selected[0].issues and selected[0].driver_dependency == dependency
    selected2, _, _ = connection_evidence(conn, config, 'INTERNET', 'Two/step', {'Step': 'getService("transaction");'}, '<opStep/>')
    assert selected2[0].driver_dependency == dependency


def test_resolved_units_verify_without_user_question_and_unresolved_ones_pause(tmp_path, monkeypatch):
    conn, config, settings, closure, original = setup_unit(tmp_path)
    monkeypatch.setattr('runtime.behavior_conversion.driver_resolution.verify_driver_load', lambda *args: None)
    unit = attach_unit_connections(conn, config, closure, original, settings)
    factory = lambda p, root, name: ManagedBuildContext(str(root / 'pom.xml'), Verifier())
    units = {unit.unit_id: unit}
    assert resolve_pending_connections(conn, config, settings, tmp_path / 'run', units, factory)
    assert pending_questions(conn, config.run_id) == []
    assert unit.service_connections[0]['ownership']['driver_verification']['platform_load_verified']
    bad = original.model_copy(update={'sources': [original.sources[0].model_copy(update={'content': 'getService("missing");'})]})
    unresolved = attach_unit_connections(conn, config, closure, bad, settings)
    assert not resolve_pending_connections(conn, config, settings, tmp_path / 'run', {unresolved.unit_id: unresolved}, factory)
    phase = conn.execute('SELECT current_phase FROM runs WHERE run_id=?', (config.run_id,)).fetchone()[0]
    assert phase == 'conversion_service_connections_pending'


def test_only_affected_connector_changes_identity_and_credentials_do_not(tmp_path):
    conn, config, settings, closure, original = setup_unit(tmp_path)
    first = attach_unit_connections(conn, config, closure, original, settings)
    pool = Path(config.source_root) / 'Project/src/Xml Definition/Channel/INTERNET/defaultFile/connectors.tmp'
    pool.write_text(pool.read_text().replace('privatePassword', 'newPassword'))
    same = attach_unit_connections(conn, config, closure, original, settings)
    assert same.fingerprint == first.fingerprint
    verify_connection_sources(config, settings, same.service_connections)
    pool.write_text(pool.read_text().replace('size="10"', 'size="20"'))
    changed = attach_unit_connections(conn, config, closure, original, settings)
    assert changed.fingerprint != first.fingerprint
    with pytest.raises(ValueError, match='evidence changed'):
        verify_connection_sources(config, settings, first.service_connections)
    plain = original.model_copy(update={'sources': []})
    assert attach_unit_connections(conn, config, closure, plain, settings) == plain


def test_production_cannot_change_driver_or_version_and_request_attachment_is_consistent(tmp_path):
    root, _, _, _ = workspace(tmp_path)
    connection = resolve(root, 'getService("regular");')[0].model_dump()
    expected = MavenDependency.model_validate(connection['driver_dependency'])
    validate_connection_wiring({}, [expected], [connection])
    with pytest.raises(ValueError, match='must match connector'):
        validate_connection_wiring({}, [expected.model_copy(update={'version': 'wrong'})], [connection])
    with pytest.raises(ValueError, match='contradicts discovered'):
        validate_connection_wiring({'src/main/resources/application.properties': 'spring.datasource.driver-class-name=${DRIVER:another.Driver}'}, [expected], [connection])
    payload = {'known_dependencies': [expected.model_copy(update={'version': 'wrong'}).model_dump()]}
    with pytest.raises(ValueError, match='version conflicts'):
        attach_connections(payload, [connection])
    known = expected.model_dump()
    known['scope'] = 'runtime'
    payload = {'known_dependencies': [known]}
    connection['driver_dependency']['scope'] = 'compile'
    attach_connections(payload, [connection])
    assert payload['known_dependencies'][0]['scope'] == 'compile'
    assert known['scope'] == 'runtime'
    connection['connector_configuration']['databaseURL'] = {'deployment_setting': 'databaseURL', 'scheme': ['jdbc', 'oracle']}
    with pytest.raises(ValueError, match='URL scheme'):
        validate_connection_wiring({'src/main/resources/application.properties':
            'spring.datasource.url=${DB_URL:jdbc:other:host}'}, [expected.model_copy(update={'scope': 'compile'})], [connection])


@pytest.mark.parametrize('filename', ['dseConnector.tmp', 'dseConnector.xml'])
@pytest.mark.parametrize('contents', [None, '<malformed privatePassword', '<XML secret="privatePassword" endpoint="privateEndpoint"/>'])
def test_deployment_connector_is_never_opened_or_required_for_conversion(tmp_path, monkeypatch, filename, contents):
    conn, config, settings, closure, original = setup_unit(tmp_path)
    root = Path(config.source_root)
    channel = root / 'Project/src/Xml Definition/Channel/INTERNET'
    registry = channel / 'dse.ini'
    registry.write_text(registry.read_text().replace('connectors.tmp', filename))
    connector = channel / 'defaultFile' / filename
    if contents is not None:
        connector.write_text(contents)
    service = root / 'Project/src/example/RegularService.java'
    service.write_text('package example; public class RegularService { '
        'public void configure(){ config.getInt("timeout"); config.getProperty("databaseURL"); '
        'config.getValueAt("dynamicSetting"); } }')
    original_open = Path.open
    def guarded_open(path, *args, **kwargs):
        if path.name.lower() in {'dseconnector.tmp', 'dseconnector.xml'}:
            pytest.fail('Deployment connector was opened')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded_open)
    try:
        unit = attach_unit_connections(conn, config, closure, original, settings)
        record, = unit.service_connections
        assert not record['issues']
        assert record['deployment_requirements']
        assert record['connector_configuration'] == {}
        assert record['driver_class'] is None
        parameters = {item['name']: item for item in record['configuration_contract']['parameters']}
        assert parameters['timeout']['type'] == 'int'
        assert parameters['databaseURL']['type'] == 'String'
        assert parameters['dynamicSetting']['type'] is None
        assert all(item['required'] is None for item in parameters.values())
        payload = {}
        attach_connections(payload, unit.service_connections)
        assert 'privatePassword' not in json.dumps(payload)
        assert 'privateEndpoint' not in json.dumps(payload)
        assert 'dseConnector' not in json.dumps(payload['service_connections'])
        assert 'external_deployment_only' in json.dumps(payload)
        assert pending_questions(conn, config.run_id) == []
        verify_connection_sources(config, settings, unit.service_connections)
        with original_open(connector, 'w') as stream:
            stream.write('<XML secret="changedPrivateValue"/>')
        unchanged = attach_unit_connections(conn, config, closure, original, settings)
        assert unchanged.fingerprint == unit.fingerprint
        verify_connection_sources(config, settings, unit.service_connections)
        from runtime.service_generation.deployment_configuration import load_deployment
        project = tmp_path / 'generated'
        project.mkdir()
        item = dict(project=str(project), channel='INTERNET', operation_id='Transfer', payload=payload)
        load_deployment(item)
        import yaml
        template = project / 'connection-configuration.yaml'
        resource, = yaml.safe_load(template.read_text())['resources']
        assert resource['parameters'] == dict(timeout=None, databaseURL=None, dynamicSetting=None)
        assert resource['parameterTypes']['timeout'] == 'int'
        template.write_text('user-edited template')
        load_deployment(item)
        assert template.read_text() == 'user-edited template'
    finally:
        conn.close()


def test_connector_only_service_becomes_an_external_binding_without_guessing_implementation(tmp_path):
    root, _, channel, definitions = workspace(tmp_path)
    registry = channel / 'dse.ini'
    registry.write_text(registry.read_text().replace('connectors.tmp', 'dseConnector.tmp'))
    record, = resolve(root, 'getService("deployedOnly");')
    assert not record.issues
    assert not record.implementation and not record.driver_class
    assert record.deployment_requirements and record.configuration_contract
    (definitions / 'services.tmp').unlink()
    broken, = resolve(root, 'getService("regular");')
    assert any('loaded service document' in issue for issue in broken.issues)


def test_old_connector_evidence_is_rejected_before_model_attachment():
    with pytest.raises(ValueError, match='must be refreshed'):
        attach_connections({}, [dict(source_evidence=[dict(path='Channel/INTERNET/defaultFile/dseConnector.tmp',
            attributes=dict(privateKey='privatePassword'))])])
