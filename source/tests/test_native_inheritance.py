"""Use the real JavaParser inventory to validate inherited native contracts."""
import pytest
from models.native_unit_bundle import NativeSourceFile,NativeUnitBundle
from models.operation_data_contract import NativeApiContract
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.native_metadata import inspect_native
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.component_conversion.steps import validate_step_candidate
from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
from models.native_component_bundle import NativeComponentBundle


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


def file(name,text):
    return NativeSourceFile(path='src/main/java/com/company/generated/inheritance/'+name+'.java',content='package com.company.generated.inheritance; '+text)


def test_inherited_generic_interface_override_and_static_rules():
    sources=[file('Base','public class Base<T> { public T value(T input){return input;} public int execute(){return 0;} private int hidden(){return 1;} protected int internal(){return 1;} }'),
        file('Contract','public interface Contract { default int route(){return 1;} static int utility(){return 2;} }'),
        file('Child','public class Child extends Base<String> implements Contract { public int execute(){return 3;} }')]
    inventory=inspect_native(sources);methods=inventory['types']['com.company.generated.inheritance.Child']['methods']
    assert {m['name'] for m in methods}=={'value','execute','route'}
    value=next(m for m in methods if m['name']=='value')
    assert value['returns']=='java.lang.String' and value['parameters'][0]['type']=='java.lang.String'
    assert value['declaring_type']=='com.company.generated.inheritance.Base' and value['inherited']
    assert next(m for m in methods if m['name']=='execute')['declaring_type']=='com.company.generated.inheritance.Child'
    assert len(inventory['types']['com.company.generated.inheritance.Child']['constructors'])==1
    validate_bundle(NativeUnitBundle(files=sources),[NativeApiContract(type_name='com.company.generated.inheritance.Child',method_signatures=['public String value(String input)','public int route()'])])
    with pytest.raises(ValueError,match='missing or changed'):
        validate_bundle(NativeUnitBundle(files=sources),[NativeApiContract(type_name='com.company.generated.inheritance.Child',method_signatures=['public long execute()'])])


def test_inherited_step_contract_uses_frozen_prerequisite_without_claiming_ownership():
    base=file('Base','public class Base { public int execute(){return 0;} }')
    child=file('Child','public class Child extends Base {}')
    api=NativeApiContract(type_name='com.company.generated.inheritance.Child',method_signatures=['public int execute()'])
    validate_bundle(NativeUnitBundle(files=[child]),[api],dependency_files=[(base.path,base.content)])
    with pytest.raises(ValueError,match='Planned native API is missing'):
        validate_bundle(NativeUnitBundle(files=[child]),[NativeApiContract(type_name='com.company.generated.inheritance.Base')],dependency_files=[(base.path,base.content)])


def test_public_entry_from_nonpublic_parent_is_visible_but_parent_is_not_exported():
    sources=[file('Outer','public class Outer { private static class Base { public int execute(){return 0;} } public static class Child extends Base {} }')]
    inventory=inspect_native(sources)
    assert 'com.company.generated.inheritance.Outer.Base' not in inventory['types']
    child=inventory['types']['com.company.generated.inheritance.Outer.Child']
    assert child['methods'][0]['declaring_type']=='com.company.generated.inheritance.Outer.Base'
    validate_bundle(NativeUnitBundle(files=sources),[NativeApiContract(type_name='com.company.generated.inheritance.Outer.Child',method_signatures=['public int execute()'])])


def test_missing_step_is_implementation_feedback_but_omitted_inherited_metadata_is_not():
    def bundle(text):
        return NativeComponentBundle(files=[file('Child',text)],contracts={'step':dict(component_id='step',apis=[dict(type_name='com.company.generated.inheritance.Child',method_signatures=['public Child()'])],
            source_entry_points=['original.execute'],evidence_ids=['source'],dependencies=[],configuration_mode='specialized')})
    request={'configured_unit':{'operation_calls':[]}}
    with pytest.raises(ImplementationInterfaceError):validate_step_candidate(bundle('public class Child {}'),request,{})
    base=file('Base','public class Base { public int execute(){return 0;} }')
    with pytest.raises(ValueError,match='metadata must expose') as error:
        validate_step_candidate(bundle('public class Child extends Base {}'),request,{base.path:base.content})
    assert not isinstance(error.value,ImplementationInterfaceError)


@pytest.mark.parametrize('element,accepted', [('String',True), ('Object',False), ('',False)])
def test_inherited_collection_keeps_element_type_for_boundary_validation(element,accepted):
    from types import SimpleNamespace
    from runtime.behavior_conversion.typed_boundaries import validate_typed_boundary,TypedBoundaryError
    result='java.util.List'+('<'+element+'>' if element else '')
    sources=[file('Base','public class Base { public '+result+' values() { return null; } }'),
             file('Child','public class Child extends Base {}')]
    inventory=inspect_native(sources)
    api=next(NativeApiContract.model_validate(api) for api in inventory['apis']
             if api['type_name'].endswith('.Child'))
    signature=next(s for s in api.method_signatures if 'values(' in s)
    assert ('<java.lang.'+element+'>') in signature if element else '<' not in signature
    output=SimpleNamespace(files=sources,unit_contract=SimpleNamespace(apis=[api]))
    if accepted:
        validate_typed_boundary(output,{'version':'typed-boundary-v1'})
    else:
        with pytest.raises(TypedBoundaryError):
            validate_typed_boundary(output,{'version':'typed-boundary-v1'})


def test_test_parser_records_native_static_settings_calls_and_explicit_static_imports():
    text='''import com.company.generated.Settings;
    import static org.junit.jupiter.api.Assertions.*;
    import static com.company.generated.Settings.configure;
    public class Probe {
      public void check() { Settings.configure(null); configure(null);
          com.company.generated.Settings.configure(null); }
    }'''
    source=NativeSourceFile(path='src/test/java/com/company/generated/inheritance/Probe.java',
        content='package com.company.generated.inheritance; '+text)
    parsed=inspect_native([source])
    calls=[call for call in parsed['calls'] if call['method']=='configure']
    assert len(calls)==3 and all(call['receiver_type']=='com.company.generated.Settings' for call in calls)
