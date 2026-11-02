"""Adapter and readiness checks share exact Java/XML context-key evidence."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from models.boundary_case import BoundaryCase
from models.native_implementation import NativeImplementation
from models.native_unit_bundle import NativeUnitBundle
from models.native_verification_binding import NativeVerificationBinding
from runtime.behavior_conversion.context_key_evidence import with_context_key_evidence
from runtime.behavior_conversion.executable_adapters import resolve_adapter
from runtime.behavior_conversion.settings_readiness import prepare_settings
from runtime.behavior_conversion.failure_routing import AdapterRepairRequired
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from runtime.behavior_conversion.adapter_configuration import resolve_configuration
from runtime.component_conversion.partition_requests import partition_request
from runtime.component_conversion.scope import partition_task
from test_component_partitions import original_request

OWNER='com.company.generated.Formatter'
SETTINGS='com.company.generated.Settings'
TARGET='legacy.Settings.configure'


def configured():
    return dict(unit_id='response',kind='response_format',requirements={'r':'Preserve'},sources=[dict(identity='original',content='original Java')],
        effective_configuration=dict(tag='Root',attributes={'dataName':'Reply'},children=[
            dict(tag='Field',attributes={'dataName':'ErrorCategory'},children=[])]),referenced_definitions=[])


def parsed():
    return dict(context_keys=[dict(name='CHANNEL_NAME',source='original',method='getValueAt')],
        apis=[dict(type_name=OWNER,method_signatures=['public Formatter()','public String format(String value)'])],
        original_methods=[dict(target=TARGET,parameters=['java.util.Set','java.util.Set'])],types={
            OWNER:dict(constructors=[dict(parameters=[])],methods=[dict(name='format',static='false',returns='java.lang.String',
                parameters=[dict(type='java.lang.String',name='value')])]),
            SETTINGS:dict(constructors=[],methods=[dict(name='configure',static='true',returns='void',
                parameters=[dict(type='java.util.Set',name='channels'),dict(type='java.util.Set',name='excluded')])])})


def production():
    return NativeImplementation(files=[dict(path='src/main/java/com/company/generated/Formatter.java',
        content='package com.company.generated; public class Formatter { public Formatter() {} public String format(String value) { return value; } }'),
        dict(path='src/main/java/com/company/generated/Settings.java',
        content='package com.company.generated; public class Settings { public static void configure(java.util.Set<String> a, java.util.Set<String> b) {} }')])


def binding(key='ErrorCategory'):
    return NativeVerificationBinding(owner_type=OWNER,method_name='format',
        arguments=[dict(type_name='java.lang.String',source='context',key=key)],
        settings_bindings={TARGET:{'class':SETTINGS,'method':'configure'}})


def bundle(value):
    return NativeUnitBundle(files=production().files,verification_binding=value,
        unit_contract=dict(unit_id='response',apis=parsed()['apis'],requirements={'r':'Preserve'},evidence_ids=['original']))


def test_java_records_and_xml_paths_are_preserved_without_mutation_or_inference():
    unit=configured();inventory=parsed();before=deepcopy((unit,inventory))
    result=with_context_key_evidence(unit,inventory)
    assert result['context_keys']==[inventory['context_keys'][0],
        dict(name='ErrorCategory',source='resolved_configuration',path=['Reply','ErrorCategory'],unit_id='response')]
    assert with_context_key_evidence(unit,result)==result
    assert (unit,inventory)==before
    result['context_keys'][0]['name']='changed'
    assert inventory==before[1]
    assert 'value' not in {key['name'] for key in result['context_keys']}


def test_duplicate_xml_leaf_names_keep_distinct_paths_and_java_provenance():
    unit=configured();unit['effective_configuration']['children']=[
        dict(attributes={'dataName':parent},children=[dict(attributes={'dataName':'ErrorCategory'})])
        for parent in ['First','Second']]
    inventory=parsed();inventory['context_keys'].append(dict(name='ErrorCategory',source='original',method='getValueAt'))
    records=with_context_key_evidence(unit,inventory)['context_keys']
    assert [key['path'] for key in records if key.get('source')=='resolved_configuration']==[
        ['Reply','First','ErrorCategory'],['Reply','Second','ErrorCategory']]
    assert any(key.get('source')=='original' and key['name']=='ErrorCategory' for key in records)


@pytest.mark.parametrize('selector',[[],[0,2]])
def test_partition_evidence_comes_from_the_trusted_resolved_tree(selector):
    original=original_request();tree=original['configured_format']['effective_configuration']
    for index,child in enumerate(tree['children'][0]['children']):child['attributes']['dataName']='Field'+str(index)
    request=partition_request(original,tree,selector,{})
    with partition_task(request['group_id'],request,original):
        unit,_=resolve_configuration(request)
    keys=with_context_key_evidence(unit,{'context_keys':[]})['context_keys']
    assert {key['name'] for key in keys}==({'Field'+str(index) for index in range(8)} if not selector else {'Field2'})
    assert len(keys)==(8 if not selector else 1)
    assert all(key['source']=='resolved_configuration' for key in keys)


def test_referenced_fields_resolve_and_missing_or_cyclic_definitions_fail():
    unit=configured();unit['effective_configuration']=dict(reference_definition_id='ref')
    unit['referenced_definitions']=[dict(definition_id='ref',attributes={'dataName':'ReferencedKey'})]
    assert with_context_key_evidence(unit,{})['context_keys'][0]['name']=='ReferencedKey'
    unit['referenced_definitions']=[]
    with pytest.raises(ValueError,match='Unavailable/cyclic'):with_context_key_evidence(unit,{})
    unit['referenced_definitions']=[dict(definition_id='ref',reference_definition_id='ref')]
    with pytest.raises(ValueError,match='Unavailable/cyclic'):with_context_key_evidence(unit,{})


@pytest.mark.parametrize('key',['ErrorCategory','CHANNEL_NAME'])
def test_adapter_and_readiness_accept_the_same_xml_and_java_keys(monkeypatch,key):
    unit=configured();inventory=parsed();before=deepcopy(inventory);calls=[]
    controls=[dict(target=TARGET,arity=2)]
    def ask(stage,request,instruction,schema,check):
        assert stage=='adapter'
        assert {record['name'] for record in request['parsed_apis']['context_keys']}=={'CHANNEL_NAME','ErrorCategory'}
        calls.append(stage)
        value=schema(binding=binding(key));check(value);return value
    selected=resolve_adapter(SimpleNamespace(ask=ask),dict(unit,runtime_controls=controls),production(),inventory,
        repair_feedback={'errors':['Repair settings wiring']})
    monkeypatch.setattr('runtime.behavior_conversion.native_metadata.inspect_native',lambda *args:deepcopy(inventory))
    monkeypatch.setattr('runtime.behavior_conversion.settings_readiness.controlled_cases',lambda *args,**kwargs:[BoundaryCase(case_id='prepared')])
    receipt=prepare_settings(unit,None,bundle(selected),controls)
    assert receipt['case_count']==1 and receipt['settings_targets']==[TARGET]
    assert calls==['adapter'] and inventory==before


@pytest.mark.parametrize('key',['InventedKey','errorcategory','value'])
def test_unknown_case_changed_and_native_parameter_names_are_rejected_by_both_checks(monkeypatch,key):
    unit=configured();inventory=parsed();controls=[dict(target=TARGET,arity=2)]
    def ask(stage,request,instruction,schema,check):
        value=schema(binding=binding(key));check(value);return value
    with pytest.raises(VerificationIncomplete,match='known original scalar key'):
        resolve_adapter(SimpleNamespace(ask=ask),dict(unit,runtime_controls=controls),production(),inventory,
            repair_feedback={'errors':['Repair wiring']})
    with pytest.raises(AdapterRepairRequired,match='known original scalar key'):
        prepare_settings(unit,None,bundle(binding(key)),controls,inventory=inventory)


def test_absent_xml_does_not_create_keys_from_native_api_names():
    inventory=parsed()
    assert with_context_key_evidence({},inventory)['context_keys']==inventory['context_keys']


def test_repaired_xml_binding_finishes_readiness_without_repeating_adapter_requests(monkeypatch):
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.behavior_conversion.stage_readiness import prepare_metadata
    from tools.component_inventory_tools.identity import stable_id
    from tools.state_store_tools import staged_conversion_state as state
    from tests.runtime.test_behavior_conversion import state as database
    conn,config=database();unit=configured();inventory=parsed();calls=[]
    controls=[dict(target=TARGET,arity=2)];code=production();output=bundle(binding())
    output.verification_binding.settings_bindings={}
    monkeypatch.setattr('runtime.behavior_conversion.settings_readiness.controlled_cases',lambda *args,**kwargs:[BoundaryCase(case_id='prepared')])
    def ask(stage,request,instruction,schema,check):
        calls.append(stage)
        value=schema(binding=binding());check(value);return value
    tasks=SimpleNamespace(conn=conn,config=config,identity='unit',revision='r',fresh=lambda:None,
        profile=PipelineConfiguration(),ask=ask)
    proof=dict(production_hash=stable_id(code.model_dump(mode='json')),validation={'build_passed':True})
    state.retain(conn,config.run_id,'unit','r','compile',proof,stable_id(proof))
    before=code.model_dump_json()
    try:
        def prepared(candidate):prepare_settings(unit,None,candidate,controls,inventory=inventory)
        receipt=prepare_metadata(tasks,dict(configured_format=unit,requirements=unit['requirements'],sources=unit['sources']),
            code,inventory,output,prepared)
        assert calls==['adapter'] and receipt['acceptance'] is False
        assert state.read(conn,config.run_id,'unit','r','implementation_ready')['status']=='retained'
        assert code.model_dump_json()==before
        assert conn.execute("SELECT count(*) FROM staged_conversion_tasks WHERE stage='failure_routes'").fetchone()[0]==0
    finally:conn.close()
