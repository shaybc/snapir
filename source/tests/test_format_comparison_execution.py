"""Exercise shared adapters with real Java, context-dependent branches and unchanged inputs."""
from pathlib import Path
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.format_comparison_plan import FormatComparisonPlan
from runtime.format_comparison.planning import original_unit
from runtime.format_comparison.runner import run_comparison
from runtime.java_toolchain import java_scope
from test_behavior_verification_boundaries import boundary_tool, source


@pytest.fixture(scope='module', autouse=True)
def selected_jdk():
    with java_scope(PipelineConfiguration(java_version=25)):
        yield


def demo_sources():
    root = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace/WSBCC_XML/src'
    return [source(name, next(root.rglob(name + '.java')).read_bytes().decode('utf-8')) for name in
            ('Context', 'Tag', 'AbstractFormatElement', 'FormatDecoratorHolder', 'AttributeXmlFormatDecoratorImpl', 'DemoXml')]


def channel_case():
    original = '''package example; import com.ibm.dse.base.*;
public class ChannelFormat {private String name; public void initializeFrom(Tag tag){name=tag.getAttribute("dataName");}
 public String format(Context context){String channel=(String)context.getValueAt("runtime.channel");
 if(channel==null)throw new IllegalArgumentException("missing channel",new IllegalStateException("channel cause"));
 return "<"+name+">"+("INTERNET".equals(channel)?"online":"branch")+"</"+name+">";}
 public void unformat(String xml,Context context){context.setValueAt(name,xml);}}
'''
    native = '''package nativecode; public class ChannelFormat {private final String name;
 public ChannelFormat(String name){this.name=name;} public String format(String channel){
 if(channel==null)throw new IllegalArgumentException("missing channel",new IllegalStateException("channel cause"));
 return "<"+name+">"+("INTERNET".equals(channel)?"online":"branch")+"</"+name+">";}}
'''
    unit = original_unit([*demo_sources(), source('format', original)], dict(java_class='example.ChannelFormat', attributes={'dataName': 'result'}))
    citation = dict(source_identity='format', excerpt='"INTERNET".equals(channel)')
    return FormatComparisonPlan(label='channel-dependent-format', scope='basic', original_unit=unit,
        native_sources=[dict(path='src/main/java/nativecode/ChannelFormat.java', content=native)],
        entries={'write': dict(direction='format', binding=dict(owner_type='nativecode.ChannelFormat', method_name='format',
            constructor_arguments=[dict(type_name='java.lang.String', source='configuration', key='dataName')],
            arguments=[dict(type_name='java.lang.String', source='context', key='runtime.channel')]))},
        cases=[dict(case_id='internet', binding_id='write', initial_context={'runtime.channel': 'INTERNET'}),
               dict(case_id='sme', binding_id='write', initial_context={'runtime.channel': 'SME'}),
               dict(case_id='null-channel', binding_id='write', initial_context={'runtime.channel': None})],
        discovery=dict(requirements=[dict(requirement_id='channel', context_key='runtime.channel', value_type='string', citations=[citation])]))


@pytest.mark.parametrize('collect_facts,verification_mode', [(True,'checklist_v1'), (False,'checklist_v1'), (False,'test_based_v1')])
def test_channel_context_runs_both_branches_without_a_format_specific_adapter(boundary_tool, tmp_path, collect_facts, verification_mode):
    plan = channel_case(); before = plan.model_dump_json()
    profile = PipelineConfiguration(java_version=25, format_comparison={'enabled': True, 'collect_facts': collect_facts},
        executable_verification={'mode':verification_mode})
    report = run_comparison(plan, profile, tmp_path / 'channel', tool=boundary_tool)
    assert report['status'] == 'completed', report
    assert report['counts']['matched'] == 3, report
    assert report['cases'][0]['legacy']['output'] == '<result>online</result>'
    assert report['cases'][1]['legacy']['output'] == '<result>branch</result>'
    assert report['cases'][2]['legacy']['exception']['causes'][0]['type'] == 'java.lang.IllegalStateException'
    assert report['cases'][2]['status'] == 'matched'
    assert report['cases'][2]['native']['exception']['causes'][0]['type'] == 'java.lang.IllegalStateException'
    assert report['inputs_unchanged'] and plan.model_dump_json() == before
    assert not report['conversion_resumed'] and not report['acceptance_changed']
    assert report['fact_validation'] == 'not_run' and not report['fact_validation_blocking']
    assert report['fact_collection'] == ('enabled' if collect_facts else 'disabled' if verification_mode=='test_based_v1' else 'disabled_for_test')
    if not collect_facts:
        assert not any(probe['id'].startswith('check-') for case in report['cases'] for probe in case['legacy']['probes'])
    else:
        assert any(probe['id'].startswith('check-') for case in report['cases'] for probe in case['legacy']['probes'])


def test_disabled_diagnostics_do_not_execute(tmp_path):
    with pytest.raises(ValueError, match='disabled'):
        run_comparison(channel_case(), PipelineConfiguration(), tmp_path / 'off')
    assert not (tmp_path / 'off').exists()


def test_string_roundtrip_and_null_result_use_the_same_adapters(boundary_tool, tmp_path):
    root = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace/WSBCC_XML/src'
    sources = [*demo_sources(), source('string', next(root.rglob('CCString.java')).read_bytes().decode('utf-8'))]
    native = '''package nativecode;public class StringFormat {private String name;
 public void setName(String value){name=value;} public String format(String value){
 return value==null?"<"+name+"/>":"<"+name+">"+value+"</"+name+">";}
 public String unformat(String xml){if(xml!=null&&xml.contains("/>") )return "";if(xml==null||!xml.contains("<"+name+">"))return null;
 return xml.substring(xml.indexOf(">")+1,xml.lastIndexOf("<"));}}'''
    def binding(method):
        return dict(owner_type='nativecode.StringFormat', method_name=method,
                    configuration_setters={'setName': dict(type_name='java.lang.String', source='configuration', key='dataName')},
                    arguments=[dict(type_name='java.lang.String', source='context', key='value')] if method == 'format' else
                              [dict(type_name='java.lang.String', source='xml')],
                    context_writes=[] if method == 'format' else [dict(context_key='value', source='result')])
    plan = FormatComparisonPlan(label='string-format', scope='basic',
        original_unit=original_unit(sources, dict(java_class='com.ibm.il.dse.cc.format.CCString', attributes={'dataName': 'value'})),
        native_sources=[dict(path='src/main/java/nativecode/StringFormat.java', content=native)],
        entries={'write': dict(direction='format', binding=binding('format')), 'read': dict(direction='unformat', binding=binding('unformat'))},
        cases=[dict(case_id='roundtrip', binding_id='write', roundtrip_binding_id='read', initial_context={'value': 'alpha'}),
               dict(case_id='empty-output', binding_id='read', input_xml='<value/>'),
               dict(case_id='null-output', binding_id='read', input_xml=None)])
    report = run_comparison(plan, PipelineConfiguration(java_version=25, format_comparison={'enabled': True}), tmp_path / 'string', tool=boundary_tool)
    assert report['counts']['matched'] == 3, report
    assert report['cases'][0]['roundtrip']['legacy']['context']['value'] == 'alpha'
    assert report['cases'][1]['native']['context']['value'] == ''
    assert report['cases'][2]['native']['context']['value'] is None


def test_configured_collection_executes_child_tree_and_compares_structured_rows(boundary_tool, tmp_path):
    root = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace/WSBCC_XML/src'
    sources = demo_sources() + [source(name, next(root.rglob(name + '.java')).read_bytes().decode('utf-8')) for name in ('CCIColl', 'CCXML', 'CCString')]
    field = dict(java_class='com.ibm.il.dse.cc.format.CCString', attributes={'dataName': 'value'})
    child = dict(java_class='com.ibm.il.dse.cc.format.CCXML', attributes={'dataName': 'row'}, children=[field])
    config = dict(java_class='com.ibm.il.dse.cc.format.CCIColl', attributes={'dataName': 'rows', 'times': '1'}, children=[child])
    # This fixture is production-side composition, not adapter logic. It deliberately ignores the second row like times=1.
    native = '''package nativecode;import java.util.*;public class Rows {
 public String format(List<Map<String,Object>> rows){if(rows==null||rows.isEmpty())return "";
 return "<row><value>"+rows.get(0).get("value")+"</value></row>";}
 public List<Map<String,Object>> unformat(String xml){if(xml==null||xml.isEmpty())return new ArrayList<>();
 int begin=xml.indexOf("<value>")+7,end=xml.indexOf("</value>");
 return List.of(Map.of("value",xml.substring(begin,end)));}}'''
    plan = FormatComparisonPlan(label='structured-collection', scope='configured', original_unit=original_unit(sources, config),
        native_sources=[dict(path='src/main/java/nativecode/Rows.java', content=native)],
        entries={'write': dict(direction='format', binding=dict(owner_type='nativecode.Rows', method_name='format',
                      arguments=[dict(type_name='java.util.List', source='context', key='rows')])),
                 'read': dict(direction='unformat', binding=dict(owner_type='nativecode.Rows', method_name='unformat',
                      arguments=[dict(type_name='java.lang.String', source='xml')], context_writes=[dict(context_key='rows', source='result')]))},
        cases=[dict(case_id='two-rows', binding_id='write', initial_context={'rows': [{'value': 'one'}, {'value': 'two'}]}, roundtrip_binding_id='read')])
    report = run_comparison(plan, PipelineConfiguration(java_version=25, format_comparison={'enabled': True}), tmp_path / 'rows', tool=boundary_tool)
    assert report['counts']['matched'] == 1, report
    assert report['cases'][0]['legacy']['output'] == '<row><value>one</value></row>'
    assert report['cases'][0]['roundtrip']['native']['context']['rows'] == [{'value': 'one'}]
    wrong_shape = plan.model_copy(deep=True)
    wrong_shape.native_sources[0].content = native.replace('List<Map<String,Object>> rows', 'List<String> rows').replace('rows.get(0).get("value")', 'rows.get(0)')
    unavailable = run_comparison(wrong_shape, PipelineConfiguration(java_version=25, format_comparison={'enabled': True}),
                                 tmp_path / 'rows-incompatible', tool=boundary_tool)
    assert unavailable['counts']['comparison_unavailable'] == 1, unavailable
    assert unavailable['cases'][0]['native']['exception'] is None

