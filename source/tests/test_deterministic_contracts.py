"""Parser-owned contracts cannot be invented or copied incorrectly by model responses."""
import pytest
from models.native_implementation import NativeImplementation
from models.native_unit_bundle import NativeUnitBundle
from models.native_component_bundle import NativeComponentBundle
from models.staged_metadata import deterministic_metadata_schema,metadata_schema
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.native_metadata import inspect_native
from runtime.behavior_conversion.deterministic_contracts import derive
from runtime.behavior_conversion.metadata_semantics import materialize
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete


def inventory():
    """Use actual JavaParser results, including a prerequisite and an unused helper."""
    def source(name,body):return dict(path='src/main/java/example/'+name+'.java',content='package example; '+body)
    files=[source('Formatter','public class Formatter { public String format(Input value){ return value.getName(); } public java.util.List<Output> results(){return null;} }'),
        source('Input','public class Input { public String getName(){return "a";} }'),
        source('Output','public class Output { public String getValue(){return "c";} }'),
        source('Helper','public class Helper { public int number(){return 8;} }')]
    dependency=source('Prerequisite','public class Prerequisite { public String value(){return "b";} }')
    production=NativeImplementation(files=files)
    with java_scope(PipelineConfiguration(java_version=25)):
        parsed=inspect_native([*production.files,NativeImplementation(files=[dependency]).files[0]])
    return production,parsed


@pytest.fixture(scope='module')
def parsed():return inventory()


def test_unit_api_closure_is_local_and_excludes_unrelated_types(parsed):
    production,inventory=parsed
    details=deterministic_metadata_schema(NativeUnitBundle)
    value=details.model_validate(dict(verification_binding={'owner_type':'example.Formatter','method_name':'format'}))
    raw=derive(value,{},inventory,production)
    assert raw['unit_contract']['api_types']==['example.Formatter','example.Input','example.Output']
    payload=dict(unit_id='original-unit',requirements={'business':'Preserve'},evidence_ids=['original-source'],
        executable_verification={'mode':'executable_boundary_v1'},converted_dependency_apis=[{'unit_id':'dependency'}])
    result=materialize(metadata_schema(NativeUnitBundle,True).model_validate(raw),payload,inventory,production)
    contract=result['unit_contract']
    assert contract['unit_id']=='original-unit' and contract['evidence_ids']==['original-source']
    assert contract['dependency_units']==['dependency'] and contract['requirements']==payload['requirements']
    assert contract['apis']==[a for a in inventory['apis'] if a['type_name'] in {'example.Formatter','example.Input','example.Output'}]


def test_component_assignment_fills_known_fields_and_excludes_prerequisites(parsed):
    production,inventory=parsed
    value=deterministic_metadata_schema(NativeComponentBundle).model_validate({'component_details':{}})
    expected={'component_id':'known-id','source_entry_points':['original.format'],'evidence_ids':['source'],
        'dependencies':['pinned-dependency'],'configuration_mode':'parameterized'}
    payload={'expected_contract_fields':{'known-id':expected}}
    raw=derive(value,payload,inventory,production)
    result=materialize(metadata_schema(NativeComponentBundle,True).model_validate(raw),payload,inventory,production)
    contract=result['contracts']['known-id']
    assert all(contract[key]==value for key,value in expected.items())
    assert {a['type_name'] for a in contract['apis']}=={'example.Formatter','example.Input','example.Output','example.Helper'}
    assert derive(value,payload,inventory,production)==raw


@pytest.mark.parametrize('field,value',[('unit_contract',{}),('api_types',['invented.Type']),('evidence_ids',['invented'])])
def test_known_contract_fields_are_not_model_response_fields(field,value):
    with pytest.raises(ValueError):deterministic_metadata_schema(NativeUnitBundle).model_validate({field:value})


def test_ambiguous_ownership_and_nonowned_entry_are_not_guessed(parsed):
    production,inventory=parsed
    schema=deterministic_metadata_schema(NativeUnitBundle)
    with pytest.raises(VerificationIncomplete,match='unique owned'):derive(schema(),{},inventory,production)
    with pytest.raises(ValueError,match='parsed, owned'):
        derive(schema(verification_binding={'owner_type':'example.Prerequisite','method_name':'value'}),{},inventory,production)
    component=deterministic_metadata_schema(NativeComponentBundle)(component_details={})
    with pytest.raises(VerificationIncomplete,match='exactly one'):
        derive(component,{'expected_contract_fields':{'a':{},'b':{}}},inventory,production)
