"""Resolve real inherited/delegated field lifecycles and compare independent native APIs."""
from copy import deepcopy
from pathlib import Path

import pytest

from models.pipeline_configuration import PipelineConfiguration
from models.format_comparison_plan import FormatComparisonPlan
from runtime.format_comparison.runner import run_comparison
from runtime.java_toolchain import java_scope
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.format_lifecycle import basic_identity
from test_behavior_verification_boundaries import boundary_tool, source, unit, prepared
from test_format_comparison_execution import demo_sources


@pytest.fixture(scope='module', autouse=True)
def selected_jdk():
    with java_scope(PipelineConfiguration(java_version=25)):
        yield


def lifecycle_sources():
    return demo_sources() + [
        source('element', 'package example; public class DataElement {}'),
        source('field', """package example; public class DataField extends DataElement {
            private String value; public DataField(String value){this.value=value;}
            public String getValue(){return value;} public void setValue(String value){this.value=value;}}
        """),
        source('logic', """package example; public class Business {
            public String formatField(DataField field){return field.getValue().trim()+"!";}
            public DataField unformatField(String wire,DataField field){
                if(wire.equals("bad"))throw new IllegalArgumentException("invalid");
                field.setValue(wire.trim());return field;}}
        """),
        source('holder', """package example; import com.ibm.dse.base.Context;
            public class Holder {
                private final Business delegate=new Business();
                public String formatField(DataField field){return delegate.formatField(field);}
                public String beforeFormatDo(DataElement field,Context context){return delegate.formatField((DataField)field);}
                public DataField unformatField(String wire,DataField field){return delegate.unformatField(wire,field);}}
        """),
        source('string', 'package example; public class CCString extends Holder {}'),
        source('writer', 'package example; import com.ibm.dse.base.Context; public class Writer {public String write(Holder holder,DataElement field,Context context){return holder.beforeFormatDo(field,context);}}'),
    ]


def field_unit(direction='response_format'):
    value=unit(direction,name='example.CCString',sources=lifecycle_sources())
    value.update(format_scope='basic',effective_configuration=dict(java_class='example.CCString',attributes=dict(dataName='field')))
    return value


@pytest.mark.parametrize('kind,method', [('response_format','beforeFormatDo'),('request_unformat','unformatField')])
def test_inherited_entry_keeps_delegated_body_in_graph(boundary_tool,kind,method):
    value=field_unit(kind)
    report=build_boundary_report(prepared(value),tool_jar=boundary_tool)
    boundary=report['boundaries'][value['unit_id']]
    assert boundary['analysis_status']=='identified', boundary['issues']
    lifecycle=boundary['format_lifecycle']
    assert lifecycle['invocations'][-1]['method']==method
    assert lifecycle['invocations'][-1]['declaring_class']=='example.Holder'
    assert any(node['declaring_class']=='example.Business' for node in boundary['reachable_slice']['nodes'])


def test_basic_discovery_does_not_require_successful_whole_format(boundary_tool):
    value=field_unit('request_unformat')
    value.pop('format_scope')
    value['effective_configuration']=dict(java_class='example.MissingRoot',attributes={},children=[
        dict(java_class='example.CCString',attributes=dict(dataName='field'))])
    value['sources'].append(source('root','package example; public class MissingRoot {}'))
    report=build_boundary_report(prepared(value),tool_jar=boundary_tool)
    assert report['counts']['identified']==0
    basic=report['basic_boundaries'][basic_identity(value['unit_id'],'example.CCString')]
    assert basic['analysis_status']=='identified',basic['issues']


def test_standalone_field_format_and_unformat_use_independent_native_api(boundary_tool,tmp_path):
    value=field_unit()
    codec='package nativecode; public class Codec {\n        public static String write(String value){return value.trim()+"!";}\n        public static String read(String value){if(value.equals("bad"))throw new IllegalArgumentException("invalid");return value.trim();}}\n'
    recipe=dict(type_name='example.DataField',source='object',arguments=[dict(type_name='java.lang.String',source='context',key='raw')])
    entries={name:dict(direction=direction,binding=dict(owner_type='nativecode.Codec',method_name=method,
        static_method=True,arguments=[dict(type_name='java.lang.String',source=origin,**({'key':'raw'} if origin=='context' else {}))]))
        for name,direction,method,origin in [('write','format','write','context'),('read','unformat','read','xml')]}
    cases=[dict(case_id='write',binding_id='write',initial_context={'raw':' value '},original_inputs={'field':recipe},observe_context_keys=[]),
           dict(case_id='read',binding_id='read',input_xml=' value ',initial_context={'raw':''},original_inputs={'field':recipe},observe_context_keys=[]),
           dict(case_id='invalid',binding_id='read',input_xml='bad',initial_context={'raw':''},original_inputs={'field':recipe},observe_context_keys=[])]
    plan=FormatComparisonPlan(label='field lifecycle',scope='basic',original_unit=value,
        native_sources=[dict(path='src/main/java/nativecode/Codec.java',content=codec)],entries=entries,cases=cases,
        original_framework=dict(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter',original_output_getters=[],original_context_getters={'field':['getValue']}))
    # Only unformat returns a field object: use a separate plan with its explicit getter projection.
    write=plan.model_copy(deep=True);write.cases=write.cases[:1]
    profile=PipelineConfiguration(java_version=25,format_comparison=dict(enabled=True,collect_facts=False))
    result=run_comparison(write,profile,tmp_path/'write',tool=boundary_tool)
    assert result['counts']['matched']==1,result
    read=plan.model_copy(deep=True);read.cases=read.cases[1:];read.original_framework.original_output_getters=['getValue']
    result=run_comparison(read,profile,tmp_path/'read',tool=boundary_tool)
    assert result['counts']['matched']==2,result


def test_hook_order_requires_resolved_original_caller(boundary_tool):
    value=field_unit('request_unformat')
    value['sources'].append(source('format-element','package example; public class FormatElement {}'))
    value['sources']=[source(item['identity'],item['content'].replace('public class Holder {',
        'public class Holder { public void beforeUnformatDo(DataElement field,FormatElement format,com.ibm.dse.base.Context context){}'))
        if item['identity']=='holder' else item for item in value['sources']]
    missing=build_boundary_report(prepared(value),tool_jar=boundary_tool)['boundaries'][value['unit_id']]
    assert 'hook order has no supplied resolved caller' in ' '.join(missing['issues'])
    value['sources'].append(source('caller',"""package example; import com.ibm.dse.base.Context;
        public class Caller { public DataField parse(Holder holder,DataField field,FormatElement format,Context context,String text){
            holder.beforeUnformatDo(field,format,context);return holder.unformatField(text,field);}}
    """))
    resolved=build_boundary_report(prepared(value),tool_jar=boundary_tool)['boundaries'][value['unit_id']]
    assert resolved['analysis_status']=='identified',resolved['issues']
    assert [call['method'] for call in resolved['format_lifecycle']['invocations']]==['beforeUnformatDo','unformatField']
    assert resolved['format_lifecycle']['ordering_evidence'][0]['source_identity']=='caller'


def test_whole_format_operation_parameter_is_not_treated_as_context(boundary_tool):
    value=field_unit('request_unformat');value.pop('format_scope')
    value['effective_configuration']=dict(java_class='example.Xml',attributes={})
    value['sources'] += [source('operation','package example; public class Operation {}'),
        source('xml','package example; public class Xml {public void unformat(String wire,Operation operation){}}')]
    boundary=build_boundary_report(prepared(value),tool_jar=boundary_tool)['boundaries'][value['unit_id']]
    assert boundary['analysis_status']=='identified',boundary['issues']
    assert boundary['format_lifecycle']['invocations'][0]['parameters']==['java.lang.String','example.Operation']


def test_ambiguous_field_overloads_remain_incomplete(boundary_tool):
    value=field_unit('response_format')
    value['effective_configuration']=dict(java_class='example.Ambiguous',attributes={})
    value['sources'] += [source('another','package other; public class DataField {}'),
        source('ambiguous',"""package example; public class Ambiguous {
            public String formatField(example.DataField value){return "a";}
            public String formatField(other.DataField value){return "b";}}
        """)]
    boundary=build_boundary_report(prepared(value),tool_jar=boundary_tool)['boundaries'][value['unit_id']]
    assert boundary['analysis_status']=='verification_incomplete'
    assert 'Ambiguous format lifecycle method' in ' '.join(boundary['issues'])


def test_component_request_uses_inherited_lifecycle_without_whole_boundary(boundary_tool,tmp_path):
    from runtime.component_conversion.requests import build_component_request
    from runtime.component_conversion.format_chain_sources import source_types
    from tools.conversion_tools.component_graph import build_component_plan
    value=field_unit('response_format');value.pop('format_scope')
    value.update(source_definition_id='format-definition',occurrence_id='format-definition',logical_id='Field')
    types=source_types(value['sources']);origins=[]
    names={item['methods'][next(iter(item['methods']))]['source_identity']:name for name,item in types.items() if item['methods'] and item['methods'][next(iter(item['methods']))] is not None}
    names.update(string='example.CCString',element='example.DataElement')
    dependencies={'example.CCString':['example.Holder'],'example.Holder':['example.Business','example.DataField','example.DataElement','com.ibm.dse.base.Context'],
                  'example.Business':['example.DataField'],'example.DataField':['example.DataElement']}
    for item in value['sources']:
        if item['identity'] not in names:continue
        path=tmp_path/(item['identity']+'.java');path.write_bytes(item['content'].encode('utf-8'))
        name=names[item['identity']]
        origins.append(dict(fqcn=name,status='verified_source',definition_id=item['identity'],source_hash=item['content_hash'],source_file=str(path),required_classes=dependencies.get(name,[])))
    preparation=dict(operations={'XML/Field':dict(status='prepared',units=[value],behavior_request=dict(java_origins=origins))})
    plan=build_component_plan(preparation['operations'])
    group=next(group for group in plan.groups if any(plan.components[key].label=='example.CCString' for key in group.members))
    report=build_boundary_report(preparation,tool_jar=boundary_tool,collect_checklists=False)
    assert report['counts']['identified']==0
    profile=PipelineConfiguration(executable_verification=dict(mode='test_based_v1'))
    request,instruction=build_component_request(plan,group,report,[],profile,check_budget=False,units={value['unit_id']:value})
    entry=next(iter(request['source_entry_points'].values()))
    assert 'example.Holder.beforeFormatDo(example.DataElement, com.ibm.dse.base.Context)' in entry
    assert request['format_lifecycles']
    assert 'do not recreate that hierarchy' in instruction


def test_chain_hook_lookup_uses_resolved_delegated_owner(boundary_tool):
    from runtime.component_conversion.format_chain_sources import source_types, resolved_lifecycle_hooks
    value=field_unit()
    value['sources']=[source(item['identity'],item['content'].replace(
        'return field.getValue().trim()+"!";', 'return applyDecorators(field.getValue().trim())+"!";').replace(
        'public class Business {', 'public class Business { public String applyDecorators(String value){return value;}'))
        if item['identity']=='logic' else item for item in value['sources']]
    boundary=build_boundary_report(prepared(value),tool_jar=boundary_tool)['boundaries'][value['unit_id']]
    hooks=resolved_lifecycle_hooks(source_types(value['sources']),boundary,'format')
    assert hooks['format']['source_identity']=='holder'
    assert hooks['applyDecorators']['source_identity']=='logic'


def test_standalone_unformat_executes_required_hook_and_rejects_missing_fixture(boundary_tool,tmp_path):
    value=field_unit('request_unformat')
    value['sources'].append(source('format-element','package example; public class FormatElement {public String getLabel(){return "field";}}'))
    value['sources']=[source(item['identity'],item['content'].replace('public class Holder {',
        'public class Holder { private boolean ready; public void beforeUnformatDo(DataElement field,FormatElement format,com.ibm.dse.base.Context context){ready=true;}').replace(
        'return delegate.unformatField(wire,field);','if(!ready)throw new IllegalStateException("hook missing");return delegate.unformatField(wire,field);'))
        if item['identity']=='holder' else item for item in value['sources']]
    value['sources'].append(source('caller',"""package example; import com.ibm.dse.base.Context;
        public class Caller { public DataField parse(Holder holder,DataField field,FormatElement format,Context context,String text){
            holder.beforeUnformatDo(field,format,context);return holder.unformatField(text,field);}}
    """))
    field=dict(type_name='example.DataField',source='object',arguments=[dict(type_name='java.lang.String',source='context',key='raw')])
    plan=FormatComparisonPlan(label='ordered hook',scope='basic',original_unit=value,
        native_sources=[dict(path='src/main/java/nativecode/Codec.java',content='package nativecode; public class Codec {public static String read(String input){return input.trim();}}')],
        entries={'read':dict(direction='unformat',binding=dict(owner_type='nativecode.Codec',method_name='read',static_method=True,
            arguments=[dict(type_name='java.lang.String',source='xml')]))},
        cases=[dict(case_id='valid',binding_id='read',input_xml=' value ',initial_context={'raw':''},observe_context_keys=[],
                    original_inputs={'field':field,'lifecycle:example.FormatElement':dict(type_name='example.FormatElement',source='object')}),
               dict(case_id='missing',binding_id='read',input_xml='value',initial_context={'raw':''},observe_context_keys=[],original_inputs={'field':field})],
        original_framework=dict(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter',original_output_getters=['getValue'],
                                original_context_getters={'field':['getValue'],'lifecycle:example.FormatElement':['getLabel']}))
    profile=PipelineConfiguration(java_version=25,format_comparison=dict(enabled=True,collect_facts=False))
    report=run_comparison(plan,profile,tmp_path/'ordered',tool=boundary_tool)
    assert report['counts']['matched']==1,report
    assert report['counts']['comparison_unavailable']==1,report
    assert 'lifecycle:example.FormatElement' in str(report['cases'][1])
