"""Verify C4 preparation with real Mapper evidence and no native generation."""

import json
from types import SimpleNamespace

import pytest

from test_scoped_closure import import_workspace
from test_scoped_vault_identity import scoped_mapper
from models.external_dependency import ExternalDependencyRule
from models.java_classpath_index import JavaClasspathIndex
from models.pipeline_configuration import PipelineConfiguration
from tools.conversion_tools.scoped_workflow.preparation import prepare_scoped_workflow
from tools.state_store_tools.operation_calls import get_contract, set_contract_status


def settings(root, vault):
    config = SimpleNamespace(run_id='scoped', source_root=str(root), vault_root=str(vault))
    profile = PipelineConfiguration(source_root=str(root), scoped_java_project='.', conversion_strategy='behavior_units',
        external_dependencies=[ExternalDependencyRule(class_name='com.ibm.il.dse.cc.cut.CCComplexOpStep', treatment='replace')])
    return config, profile


def prepare(conn, config, profile, **kwargs):
    return prepare_scoped_workflow(conn, config, profile, classpath_index=JavaClasspathIndex(), **kwargs)


def pin(conn, key='SME/Flow', application='bank'):
    from tools.state_store_tools.service_api_uses import record_service_use
    channel, operation = key.split('/', 1)
    contract = dict(application_id=application, channel=channel, operation_id=operation, api_revision='1',
        service_id='flow', artifact_reference='bank:flow:1', method='POST', path='/published/flow',
        media_types=['application/xml'], request_contract={'type': 'request'}, response_contract={'type': 'reply'},
        error_contract={'type': 'error'}, api_definition={'error_policy': 'Keep XML errors'},
        addresses={'test': {'base_url_property': 'bank.flow.base-url'}}, completion=dict(source_run_id='previous',
        validation_report_reference='reports/validated.json', conversion_passed=True, package_passed=True,
        tests_passed=True, review_approved=True, gates_approved=True))
    return record_service_use(conn, 'scoped', contract, 'test')


def test_contextual_contracts_units_routes_and_readiness(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    result = prepare(conn, config, profile)
    assert not result['conversion_enabled']
    assert all(item['status'] == 'prepared' for item in result['operations'].values()), result
    caller = result['operations']['SME/Caller']
    call = caller['calls'][0]
    assert call['callee'] == 'SME/Flow'
    assert call['service_contract']['operation'] == 'SME/Flow'
    assert call['occurrence_id'] == caller['behavior_request']['steps'][0]['occurrence_id']
    flow = result['operations']['SME/Flow']
    steps = flow['behavior_request']['steps']
    assert [step['source_index'] for step in steps] == [0, 2, 3, 4]
    assert steps[0]['business_name'] == steps[1]['business_name'] == 'Repeat'
    assert steps[0]['unit_id'] != steps[1]['unit_id']
    assert steps[0]['attributes']['fieldValue'] == 'first'
    assert steps[1]['attributes']['fieldValue'] == 'second'
    assert steps[1]['routes']['on0Do'] == steps[1]['note']
    assert steps[2]['routes']['on0Do'] == steps[0]['note']
    assert steps[-1]['routes']['onOtherDo'] is None
    assert steps[0]['return_body_switches'] != steps[1]['return_body_switches']
    assert all(identity in flow['contract']['return_body_formats'] for step in steps
               for identity in step['return_body_switches'].values())
    assert steps[0]['return_body_units'] != steps[1]['return_body_units']
    assert all(unit_id in {unit['unit_id'] for unit in flow['units']} for step in steps
               for unit_id in step['return_body_units'].values())
    assert flow['behavior_request'] == flow['assembly_request']
    assert len([key for key in flow['route_test_request']['requirements'] if key.startswith('route-')]) == 4
    assert flow['behavior_request']['context_chain'][0]['declared_fields'][0]['attributes']['value'] == 'SME'
    assert not flow['behavior_request']['conversion_enabled']
    request = flow['contract']['formats']['csRequestFormat']['effective_format']
    assert request['children'][0]['collection_kind'] == 'indexed'
    referenced = flow['contract']['formats']['csRequestFormat']['referenced_definitions']
    assert len(referenced) == 1
    assert next(iter(referenced.values()))['children'][0]['attributes']['dataName'] == 'LeafField'
    assert 'operation_calls' in caller['behavior_request']['requirements']
    assert flow['contract']['status'] == 'planned'
    set_contract_status(conn, 'scoped', 'SME/Flow', 'validated')
    again = prepare(conn, config, profile)
    assert again['operations']['SME/Flow']['contract']['status'] == 'validated'
    assert again['operations']['SME/Flow']['units'] == flow['units']
    assert conn.execute('SELECT count(*) FROM source_artifacts').fetchone()[0] == 0
    assert conn.execute('SELECT count(*) FROM operation_closures').fetchone()[0] == 0


def test_excluded_call_requires_pin_without_analyzing_or_scheduling_callee(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    # Break only the excluded implementation: a pinned service must not read it.
    (root / 'src/example/Work.java').unlink()
    report = prepare(conn, config, profile, selected={'SME/Caller'})
    item = report['operations']['SME/Caller']
    assert item['status'] == 'blocked'
    assert any('pin its published API' in issue for issue in item['blockers'])
    saved = [json.loads(row[0]) for row in conn.execute('SELECT closure_json FROM scoped_operation_closures')]
    assert [(item['channel'], item['operation_id']) for item in saved] == [('SME', 'Caller')]
    pin(conn)
    report = prepare(conn, config, profile, selected={'SME/Caller'})
    item = report['operations']['SME/Caller']
    assert item['status'] == 'prepared', item['blockers']
    assert item['calls'][0]['service_contract']['published_api']
    assert item['calls'][0]['service_contract']['path'] == '/published/flow'
    assert set(report['operations']) == {'SME/Caller'}
    pin(conn, application='another-bank')
    from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale
    with pytest.raises(ScopedCheckpointStale, match='call_bindings'):
        prepare(conn, config, profile, selected={'SME/Caller'})


def test_duplicate_calls_bind_to_occurrence_not_label(tmp_path, scoped_mapper):
    def change(root):
        path = root / 'Channel/SME/Caller.xml'
        xml = path.read_text().replace('</CCDSEServerOperation>', '''
          <opStep id="Call" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep" opExecuteName="Other" on0Do="end"/>
        </CCDSEServerOperation>''')
        path.write_text(xml)
        registry = root / 'Channel/XML/dse.ini'
        registry.write_text(registry.read_text().replace('<operDef id="Flows.xml" value="Flow"/>',
            '<operDef id="Flows.xml" value="Flow"/><operDef id="Other.xml" value="Other"/>'))
        (root / 'Channel/XML/Other.xml').write_text('''<XML><CCDSEServerOperation id="Other" operationContext="Ctx">
            <opStep id="Work" implClass="example.Work" on0Do="end"/>
            <refFormat name="csRequestFormat" refid="Req"/><refFormat name="csReplyFormat" refid="One"/>
            <refFormat name="csErrorReplyFormat" refid="Err"/></CCDSEServerOperation></XML>''')
    conn, root, vault = import_workspace(tmp_path, scoped_mapper, change=change)
    config, profile = settings(root, vault)
    report = prepare(conn, config, profile)
    caller = report['operations']['SME/Caller']
    assert caller['status'] == 'prepared', caller['blockers']
    calls = caller['calls']
    assert [call['step'] for call in calls] == ['Call', 'Call']
    assert {call['callee'] for call in calls} == {'SME/Flow', 'SME/Other'}
    assert len({call['occurrence_id'] for call in calls}) == 2
    units = caller['units']
    assert len(units) == 2
    assert all(len(unit['operation_calls']) == 1 for unit in units)
    assert len({unit['operation_calls'][0]['occurrence_id'] for unit in units}) == 2


def test_local_override_selects_contextual_contract_and_independent_units(tmp_path, scoped_mapper):
    def change(root):
        path = root / 'Channel/SME/Caller.xml'
        path.write_text(path.read_text().replace('</XML>',
            '<fmtDef id="Req"><CCString dataName="LocalOverride"/></fmtDef></XML>'))
    conn, root, vault = import_workspace(tmp_path, scoped_mapper, change=change)
    config, profile = settings(root, vault)
    report = prepare(conn, config, profile)
    local, base = (report['operations'][key] for key in ('SME/Flow', 'XML/Flow'))
    assert local['status'] == base['status'] == 'prepared'
    local_request, base_request = (item['contract']['formats']['csRequestFormat'] for item in (local, base))
    assert local_request['definition_id'] != base_request['definition_id']
    assert local_request['effective_format']['children'][0]['attributes']['dataName'] == 'LocalOverride'
    assert base_request['effective_format']['children'][0]['tag'] == 'CCIColl'
    assert local['behavior_request']['definition_id'] == base['behavior_request']['definition_id']
    assert local['behavior_request']['operation_identity'] != base['behavior_request']['operation_identity']
    assert not {unit['unit_id'] for unit in local['units']} & {unit['unit_id'] for unit in base['units']}


def test_pinned_target_does_not_propagate_selected_callee_source_failures(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    pin(conn)
    (root / 'src/example/Work.java').unlink()
    report = prepare(conn, config, profile)
    assert report['operations']['SME/Flow']['status'] == 'blocked'
    assert report['operations']['SME/Caller']['status'] == 'prepared'


def test_missing_source_project_blocks_without_enabling_generation(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    profile.scoped_java_project = None
    report = prepare(conn, config, profile)
    assert report['operations']['SME/Flow']['status'] == 'blocked'
    assert report['operations']['SME/Caller']['status'] == 'blocked'
    assert not report['conversion_enabled']


def test_endpoint_hash_encoding_and_contract_changes_preserve_existing_policy(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    prepare(conn, config, profile)
    from models.scoped_operation_closure import ScopedOperationClosure
    from tools.conversion_tools.scoped_workflow.contracts import plan_context_contracts
    row = conn.execute("SELECT closure_json FROM scoped_operation_closures WHERE json_extract(closure_json,'$.channel')='SME' AND json_extract(closure_json,'$.operation_id')='Flow'").fetchone()
    closure = ScopedOperationClosure.model_validate_json(row[0])
    key = 'SME/#Flow'
    closure = closure.model_copy(update={'operation_id': '#Flow'})
    graph = dict(operations={key: dict(source_hash='captured')}, calls=[])
    contract = plan_context_contracts(conn, 'scoped', graph, {key: closure})[key]
    assert contract['path'] == '/operations/SME/%23Flow'
    set_contract_status(conn, 'scoped', key, 'validated')
    changed = closure.model_copy(update={'evidence_hash': 'changed-context'})
    contract = plan_context_contracts(conn, 'scoped', graph, {key: changed})[key]
    assert contract['status'] == 'planned'


def test_connection_adapter_preserves_ownership_and_rejects_unchecked_support(tmp_path, monkeypatch):
    import hashlib
    from models.behavior_unit import SourceEvidence
    from models.java_source_index import JavaSourceIndex
    from models.scoped_configured_unit import ScopedConfiguredUnit
    from tools.conversion_tools.scoped_workflow import connections
    path = tmp_path / 'Work.java'
    path.write_text('class Work { void run() { getService("db"); } }')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    origin = dict(status='verified_source', definition_id='source-work', source_file=str(path), source_hash=digest)
    closure = SimpleNamespace(channel='SME', operation_id='Flow', java_origins=[origin])
    config = SimpleNamespace(run_id='scoped', source_root=str(tmp_path))
    profile = SimpleNamespace(scoped_java_project='.')
    index = JavaSourceIndex(workspace_root=str(tmp_path), source_roots={'.': [str(tmp_path)]},
        classes={'Work': [str(path)], 'OtherProject': ['other']}, class_projects={str(path): '.', 'other': 'elsewhere'})
    monkeypatch.setattr(connections, 'discover_java_sources', lambda *args: index)
    seen = {}
    record = SimpleNamespace(issues=[], supporting_sources=[str(path)], model_dump=lambda **kwargs:
        dict(connection_id='db', ownership={'scope': 'step', 'release': 'finally'}))
    def discover(*args, **kwargs):
        seen.update(kwargs)
        return [record], kwargs['source_index'], kwargs['classpath_index']
    monkeypatch.setattr(connections, 'connection_evidence', discover)
    unit = ScopedConfiguredUnit(unit_id='unit', kind='configured_step', logical_id='Repeat',
        operation_identity='context-hash', occurrence_id='occurrence-hash', source_definition_id='definition-hash',
        effective_configuration={'service': 'db'}, configuration_xml='<opStep id="Repeat"/>', fingerprint='fingerprint',
        sources=[SourceEvidence(identity='source-work', content=path.read_text(), content_hash=digest)])
    updated = connections.attach_scoped_connections(None, config, closure, unit, profile, JavaClasspathIndex())
    assert updated.service_connections[0]['ownership']['release'] == 'finally'
    assert updated.unit_id != unit.unit_id
    assert seen['persist'] is False
    assert 'OtherProject' not in seen['source_index'].classes
    record.supporting_sources = [str(tmp_path / 'unchecked.java')]
    with pytest.raises(ValueError, match='outside the checked scoped closure'):
        connections.attach_scoped_connections(None, config, closure, unit, profile, JavaClasspathIndex())


def test_scoped_unit_entry_uses_qualified_sources_without_legacy_tables(tmp_path, scoped_mapper):
    from models.scoped_operation_closure import ScopedOperationClosure
    from tools.conversion_tools.behavior_unit_builder import build_behavior_units
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    report = prepare(conn, config, profile, selected={'SME/Flow'})
    row = conn.execute('SELECT closure_json FROM scoped_operation_closures').fetchone()
    closure = ScopedOperationClosure.model_validate_json(row[0])
    units, bindings = build_behavior_units(conn, config, closure, profile)
    assert len(units) == 8
    assert bindings == report['operations']['SME/Flow']['behavior_request']['unit_bindings']
    assert len({unit.unit_id for unit in units}) == len(units)
    assert units[0].sources[0].identity == units[1].sources[0].identity


def test_cycles_block_coordination_but_backward_step_routes_do_not(tmp_path, scoped_mapper):
    def change(root):
        path = root / 'Channel/SME/Caller.xml'
        text = path.read_text().replace('opExecuteName="Flow"', 'opExecuteName="Caller"')
        text = text.replace('</CCDSEServerOperation>', '''
          <refFormat name="csRequestFormat" refid="Req"/><refFormat name="csReplyFormat" refid="One"/>
          <refFormat name="csErrorReplyFormat" refid="Err"/></CCDSEServerOperation>''')
        path.write_text(text)
    conn, root, vault = import_workspace(tmp_path, scoped_mapper, change=change)
    config, profile = settings(root, vault)
    report = prepare(conn, config, profile)
    assert report['operations']['SME/Caller']['status'] == 'blocked'
    assert any('coordinated service contracts' in issue for issue in report['operations']['SME/Caller']['blockers'])
    if 'SME/Flow' in report['operations']:
        assert report['operations']['SME/Flow']['status'] == 'prepared'


def test_selection_and_manifest_changes_are_not_guessed(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    with pytest.raises(ValueError, match='imported selection'):
        prepare(conn, config, profile, selected={'OTHER/Flow'})
    manifest = vault / 'vault-manifest.json'
    manifest.write_text(manifest.read_text() + '\n')
    with pytest.raises(ValueError, match='changed since intake'):
        prepare(conn, config, profile)


@pytest.mark.parametrize('engine', ['behavior', 'assembly'])
def test_runtime_paths_prepare_then_stop_before_models_and_component_gates(tmp_path, scoped_mapper, monkeypatch, engine):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    from tools.state_store_tools.runs import upsert_run, get_run
    upsert_run(conn, run_id='scoped', run_mode='full_inventory')
    from tools.conversion_tools.scoped_workflow import preparation
    monkeypatch.setattr(preparation, 'discover_java_classpath', lambda *args: JavaClasspathIndex())
    def forbidden(*args, **kwargs):
        pytest.fail('Generation/gate/legacy planning was invoked')
    directory = tmp_path / 'run'
    if engine == 'behavior':
        from runtime.behavior_conversion.runner import resume_behavior_pipeline
        resume_behavior_pipeline(conn, config, profile, directory, model_call=forbidden, context_factory=forbidden)
    else:
        from runtime.operation_assembly.runner import run_operation_assembly
        packet = SimpleNamespace(channel='SME', operation_id='Flow')
        plan = SimpleNamespace(run_id='scoped', batches=[SimpleNamespace(task_packets=[packet])])
        phase = run_operation_assembly(conn, config, profile, plan, directory, gate_checker=forbidden,
            plan_builder=forbidden, context_factory=forbidden, skeleton_generator=forbidden)
        assert phase == 'conversion_scoped_gated'
    assert get_run(conn, 'scoped')['current_phase'] == 'conversion_scoped_gated'
    from runtime.workspace_paths import run_report_path
    report = json.loads(run_report_path(directory, 'scoped_workflow_preparation.json').read_text())
    assert not report['conversion_enabled']
    assert 'preparation_error' not in report, report
    assert all(item['status'] == 'prepared' for item in report['operations'].values()), report


def test_checkpoint_dispatches_scoped_before_legacy_planning(tmp_path, scoped_mapper, monkeypatch):
    import constants
    from contextlib import nullcontext
    from tools.workspace_intake_tools.run_factory import create_run_config
    from tools.state_store_tools.runs import upsert_run
    from runtime.workspace_paths import run_database_path, run_profile_path, run_report_path
    from runtime import checkpoints
    from tools.conversion_tools.scoped_workflow import preparation
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    _, profile = settings(root, vault)
    directory = tmp_path / 'scoped'
    run_database_path(directory).parent.mkdir(parents=True)
    run_database_path(directory).touch()
    values = {key: getattr(constants, key) for key in dir(constants) if key.isupper()}
    values.update(COMPOSER_ROOT=str(root), VAULT_ROOT=str(vault), OUTPUT_ROOT=str(directory / 'generated'),
                  DB_PATH=str(run_database_path(directory)), RUN_MODE='full_inventory',
                  TARGET_CHANNELS=[], INCLUDE_OPERATIONS=None, EXCLUDE_OPERATIONS=None)
    config = create_run_config(values, 'scoped')
    upsert_run(conn, run_id='scoped', run_mode='full_inventory', current_phase='planning_inputs_ready', run_config=config)
    run_profile_path(directory).write_text(profile.model_dump_json())
    monkeypatch.setattr(checkpoints, 'get_connection', lambda *args: conn)
    monkeypatch.setattr(checkpoints, 'run_model_diagnostics', lambda *args: nullcontext())
    monkeypatch.setattr(checkpoints, 'java_scope', lambda *args: nullcontext())
    monkeypatch.setattr(preparation, 'discover_java_classpath', lambda *args: JavaClasspathIndex())
    monkeypatch.setattr(checkpoints, 'get_operations_for_planning', lambda *args: pytest.fail('Legacy planning invoked'))
    assert checkpoints.resume_pipeline(str(tmp_path), 'scoped') == directory
    report = json.loads(run_report_path(directory, 'scoped_workflow_preparation.json').read_text())
    assert 'preparation_error' not in report
    assert not report['conversion_enabled']
