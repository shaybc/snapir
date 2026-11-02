"""Typed generation derives contracts from evidence and rejects generic boundary replacements."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from runtime.behavior_conversion.typed_boundaries import attach_typed_boundary, validate_typed_boundary, INSTRUCTION


@pytest.mark.parametrize('kind', ['request_unformat', 'response_format', 'configured_step'])
def test_fields_and_reuse_come_from_evidence_without_user_dtos(kind):
    node = dict(attributes={'dataName':'FamilyName'}, children=[], tag='CCString')
    payload = dict(kind=kind, effective_configuration=node,
        referenced_definitions=[dict(definition_id='family-format', implementation='source')],
        converted_dependency_apis=[dict(unit_id='accepted', input_type='example.Values')])
    before = deepcopy(payload)
    assert attach_typed_boundary(payload)
    contract = payload['typed_boundary_contract']
    assert contract['configured_fields'][0]['path'] == ['FamilyName']
    assert contract['configured_fields'][0]['structure'] == {key:value for key,value in node.items() if key!='children'}
    assert contract['accepted_native_apis'] == before['converted_dependency_apis']
    assert not contract['user_supplied_dtos_required']
    contract['configured_fields'][0]['attributes']['dataName']='other'
    assert payload['effective_configuration'] == before['effective_configuration']
    assert 'family name may both be String' in INSTRUCTION


def test_component_contract_uses_configured_format_and_prerequisite_apis():
    payload = dict(kind='format_composition', configured_format=dict(kind='response_format'),
        prerequisite_components=[dict(apis=['verified-type'])])
    assert attach_typed_boundary(payload)
    assert payload['typed_boundary_contract']['output']=='xml_string'
    assert payload['typed_boundary_contract']['accepted_native_apis']==payload['prerequisite_components']
    assert not attach_typed_boundary(dict(kind='operation_assembly'))


def bundle(signature, component=False):
    api=SimpleNamespace(type_name='example.Mapper',method_signatures=[signature])
    source=SimpleNamespace(path='src/main/java/example/Mapper.java',content='''package example;
import java.util.Map; import java.util.List;
public class Mapper {}''')
    return SimpleNamespace(files=[source],unit_contract=None if component else SimpleNamespace(apis=[api]),
        contracts={'id':SimpleNamespace(apis=[api])} if component else {})


@pytest.mark.parametrize('signature', [
    'public String format(Map<String,Object> values)',
    'public java.util.HashMap execute()', 'public Object execute()',
    'public int execute(Object[] values)', 'public void execute(List values)',
    'public java.util.List values()', 'public void execute(java.util.Set)',
    'public void execute(List<Object> values)',
    'public com.fasterxml.jackson.databind.JsonNode execute()'])
def test_generic_state_is_retryable_candidate_error(signature):
    with pytest.raises(ValueError,match='Typed boundary requires'):
        validate_typed_boundary(bundle(signature),{'version':'typed-boundary-v1'})


@pytest.mark.parametrize('signature', ['public String format(example.Response values)',
    'public void unformat(String xml, example.Values state)',
    'public int execute(example.Values state)', 'public List<String> names()',
    'public String getFamilyName()', 'public Mapper()', 'public boolean equals(Object other)'])
def test_typed_values_and_collections_remain_valid(signature):
    validate_typed_boundary(bundle(signature),{'version':'typed-boundary-v1'})
    validate_typed_boundary(bundle(signature,True),{'version':'typed-boundary-v1'})


def selected_bundle(getter='String',output='String'):
    """Contracts intentionally include helpers; the typed policy must select binding members only."""
    from models.native_verification_binding import NativeVerificationBinding
    mapper=SimpleNamespace(type_name='example.Mapper',method_signatures=[
        'public '+output+' format(example.Values values)', 'public Map<String,Object> format(Map<String,Object> values)',
        'public Map<String,Object> unrelated()'])
    values=SimpleNamespace(type_name='example.Values',method_signatures=[
        'public Values()', 'public Values(Map<String,Object> values)', 'public void setValue(String value)',
        'public '+getter+' getValue()', 'public boolean hasValue()',
        'public static Values fromMap(Map<String,Object> values)', 'public Map<String,Object> toMap()'])
    result=bundle('public String unused()')
    result.files.append(SimpleNamespace(path='src/main/java/example/Values.java',
        content='package example; import java.util.Map; public class Values {}'))
    result.unit_contract.apis=[mapper,values]
    result.verification_binding=NativeVerificationBinding(owner_type='example.Mapper',method_name='format',
        arguments=[dict(type_name='example.Values',source='object',properties={
            'setValue':dict(type_name='java.lang.String',source='context',key='Value')})])
    return result


def test_bound_formatter_allows_unused_map_helpers_and_overloads():
    validate_typed_boundary(selected_bundle(),{'version':'typed-boundary-v1'})


@pytest.mark.parametrize('getter,output',[('Object','String'),('String','Map<String,Object>')])
def test_bound_formatter_still_rejects_selected_untyped_values(getter,output):
    from runtime.behavior_conversion.typed_boundaries import TypedBoundaryError
    with pytest.raises(TypedBoundaryError):
        validate_typed_boundary(selected_bundle(getter,output),{'version':'typed-boundary-v1'})


def test_projection_checks_the_selected_getter_chain_only():
    from models.native_boundary_projection import NativeBoundaryProjection
    result=selected_bundle()
    result.verification_binding.context_writes=[NativeBoundaryProjection(context_key='Value',source='argument',argument_index=0,
        getters=['toMap'])]
    with pytest.raises(ValueError,match='Typed boundary requires'):
        validate_typed_boundary(result,{'version':'typed-boundary-v1'})


def test_unbound_configured_step_ignores_inherited_service_registry_helpers():
    result=bundle('public int execute()',component=True)
    result.contracts['id'].apis[0].method_signatures.extend([
        'public int execute(example.Values values)',
        'public void setService(java.lang.String name, java.lang.Object service)',
        'public java.lang.Object getService(java.lang.String name)',
        'public java.util.Map<String,Object> unrelated()'])
    validate_typed_boundary(result,{'version':'typed-boundary-v1','kind':'configured_step'})


@pytest.mark.parametrize('signature',[
    'public int execute(Object values)',
    'public int execute(Map<String,Object> values)',
    'public Object execute()',
    'public int execute(List<Object> values)',
])
def test_unbound_configured_step_still_checks_execute_inputs_and_results(signature):
    result=bundle(signature,component=True)
    result.contracts['id'].apis[0].method_signatures.append('public void setService(String name, Object value)')
    with pytest.raises(ValueError,match='Typed boundary requires'):
        validate_typed_boundary(result,{'version':'typed-boundary-v1','kind':'configured_step'})


def test_missing_step_entry_keeps_the_existing_validation_instead_of_selecting_nothing():
    result=bundle('public void setService(String name, Object value)',component=True)
    with pytest.raises(ValueError,match='Typed boundary requires'):
        validate_typed_boundary(result,{'version':'typed-boundary-v1','kind':'configured_step'})


def test_generic_helper_is_checked_when_explicitly_selected_as_binding():
    from models.native_verification_binding import NativeVerificationBinding
    result=bundle('public Object getService(String name)',component=True)
    result.contracts['id'].apis[0].method_signatures.append('public int execute()')
    result.verification_binding=NativeVerificationBinding(owner_type='example.Mapper',method_name='getService',
        arguments=[dict(type_name='java.lang.String',source='context',key='ServiceName')])
    with pytest.raises(ValueError,match='Typed boundary requires'):
        validate_typed_boundary(result,{'version':'typed-boundary-v1','kind':'configured_step'})


def test_bound_step_still_checks_selected_projection_types():
    result=selected_bundle(getter='Object')
    result.unit_contract.apis[0].method_signatures[0]='public String execute(example.Values values)'
    result.verification_binding.method_name='execute'
    with pytest.raises(ValueError,match='Typed boundary requires'):
        validate_typed_boundary(result,{'version':'typed-boundary-v1','kind':'configured_step'})


def test_bound_step_still_checks_selected_constructor_types():
    from models.native_boundary_value import NativeBoundaryValue
    result=selected_bundle()
    result.unit_contract.apis[0].method_signatures[0]='public String execute(example.Values values)'
    result.unit_contract.apis[0].method_signatures.append('public Mapper(Object service)')
    result.verification_binding.method_name='execute'
    result.verification_binding.constructor_arguments=[NativeBoundaryValue(type_name='java.lang.Object',source='context',key='Service')]
    with pytest.raises(ValueError,match='Typed boundary requires'):
        validate_typed_boundary(result,{'version':'typed-boundary-v1','kind':'configured_step'})


def test_thin_path_supplies_accepted_sources_and_pins_without_modifying_them():
    from test_thin_path_experiment import preparation
    from tools.behavior_verification.thin_path_request import select_units, build_request
    from models.pipeline_configuration import PipelineConfiguration
    unit=select_units(preparation())[1]
    boundary=SimpleNamespace(unit_id=unit['unit_id'],source_manifest_hash='source',configuration_hash='xml')
    accepted=[dict(unit_id='previous',apis=[dict(type_name='example.Values')],
        files=[dict(path='src/main/java/example/Values.java',content='accepted source')],dependencies=[])]
    request,_=build_request(unit,boundary,[],PipelineConfiguration(),accepted=accepted)
    assert request['converted_dependency_apis']==accepted
    request['converted_dependency_apis'][0]['files'][0]['content']='changed'
    assert accepted[0]['files'][0]['content']=='accepted source'


def test_generation_corrects_generic_api_before_technical_validation():
    import json
    from tests.runtime.test_behavior_conversion import state, profile
    from models.native_unit_bundle import NativeUnitBundle
    from runtime.behavior_conversion.generation import generate
    conn,config=state()
    requests=[]; validated=[]
    def model(instruction,encoded):
        request=json.loads(encoded); requests.append(request)
        assert request['typed_boundary_contract']['kind']=='response_format'
        assert 'Response example SHAPE ONLY' in instruction
        if len(requests)>1:
            assert 'Typed boundary requires' in request['correction_feedback']
        signature='public String format(Map<String,Object> values)' if len(requests)==1 else 'public String format(String value)'
        return json.dumps(dict(files=[dict(path='src/main/java/example/Mapper.java',content='package example; import java.util.Map; public class Mapper {}')],
            unit_contract=dict(unit_id='unit',apis=[dict(type_name='example.Mapper',method_signatures=[signature])],
                requirements={'business':'Preserve source behavior'},evidence_ids=['source'])))
    try:
        generate(conn,config,profile(max_agent_task_retries=2),'unit','unit','Generate selected unit.',
            dict(kind='response_format',requirements={}),NativeUnitBundle,
            validator=lambda output,cached=False:validated.append(output),model_call=model,require_coverage=False)
        assert len(requests)==2 and len(validated)==1
    finally:
        conn.close()
