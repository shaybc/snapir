"""Check retired metadata compatibility and the ownership contracts still needed by partitions."""
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from models.native_component_bundle import NativeComponentBundle
from models.native_format_component_bundle import NativeFormatComponentBundle
from models.native_format_subtree_bundle import NativeFormatSubtreeBundle
from models.staged_metadata import deterministic_metadata_schema
from runtime.component_conversion.format_chain_ownership import chain_ownership
from tools.conversion_tools import component_identity


@pytest.mark.parametrize('schema',[NativeFormatComponentBundle,NativeFormatSubtreeBundle])
def test_historical_internal_descriptions_load_but_never_enter_new_schema_or_output(schema):
    original=dict(contracts={'component':dict(component_id='component',apis=[dict(type_name='native.Format',method_signatures=['public String format(String value)'])],source_entry_points=['original.format'],evidence_ids=['source'])},
        files=[dict(path='src/main/java/native/Format.java',content='package native; public class Format {}')],
        format_chain_bindings=[dict(calls='historical invalid structural evidence')])
    candidate=schema.model_validate(original)
    assert 'format_chain_bindings' in original
    assert 'format_chain_bindings' not in candidate.model_dump()
    assert 'format_chain_bindings' not in schema.model_json_schema()['properties']
    assert 'format_chain_bindings' not in deterministic_metadata_schema(schema,True).model_fields
    with pytest.raises(ValidationError,match='unexpected_field'):schema.model_validate(dict(original,unexpected_field=True))


def test_unrelated_bundle_contract_does_not_silently_drop_unknown_fields():
    with pytest.raises(ValidationError):NativeComponentBundle.model_validate(dict(contracts={},format_chain_bindings=[]))


def test_partition_ownership_retains_child_type_and_records_local_occurrences_without_internal_calls():
    child=dict(occurrence_id='child',group_id='child-group',type_name='native.child.Chain')
    request=dict(group_id='parent-group',native_package='native.parent',inherited_format_chain_ownership=[child],
        format_chains=[dict(occurrence_id='child',class_name='Chain'),dict(occurrence_id='parent',class_name='OtherChain')])
    assert chain_ownership(request)==[child,dict(occurrence_id='parent',group_id='parent-group',type_name='native.parent.OtherChain')]
    assert chain_ownership({})==[]


def test_parent_partition_receives_child_ownership_and_public_contracts():
    from test_component_partitions import original_request
    from runtime.component_conversion.partition_requests import partition_request
    original=original_request()
    original.update(format_chain_policy=component_identity.FORMAT_COMPOSITION_POLICY_VERSION,
        format_chains=[dict(occurrence_id='1',class_name='ChildChain')])
    ownership=dict(occurrence_id='1',group_id='child',type_name='native.child.ChildChain')
    child=dict(group_id='child',contracts={'child':dict(apis=[dict(type_name='native.child.Format')])},format_chain_ownership=[ownership])
    request=partition_request(original,original['configured_format']['effective_configuration'],(0,),{(0,1):child})
    assert request['inherited_format_chain_ownership']==[ownership]
    assert request['prerequisite_components'][-1]['contracts']==child['contracts']
    assert 'inherited_format_chain_bindings' not in request


def test_policy_revisions_invalidate_compositions_without_invalidating_basic_classes(monkeypatch):
    group=SimpleNamespace(members=['one'])
    def plan(kind):
        return SimpleNamespace(components={'one':SimpleNamespace(kind=kind,roles=['format_leaf'],model_dump=lambda **kw:dict(kind=kind))})
    basic=component_identity.input_revision(plan('java_implementation'),group,{})
    composition=component_identity.input_revision(plan('format_composition'),group,{})
    monkeypatch.setattr(component_identity,'FORMAT_COMPOSITION_POLICY_VERSION','another-composition-policy')
    assert component_identity.input_revision(plan('java_implementation'),group,{})==basic
    assert component_identity.input_revision(plan('format_composition'),group,{})!=composition
