"""Verify source-derived decorator scope, concrete compositions and complete-chain guards."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib
import pytest
from runtime.component_conversion.format_chains import configured_chains,attach_format_chains
from runtime.component_conversion.format_chain_sources import source_types,reachable_hooks

ROOT=Path(__file__).resolve().parents[2]/'bank-demo/composer/Workspace/WSBCC_XML/src'


def source(name,text):
    return dict(identity=name,content=text,content_hash=hashlib.sha256(text.encode('utf-8')).hexdigest())


def original_sources():
    return [source(str(path),path.read_bytes().decode('utf-8')) for path in ROOT.rglob('*.java')]


def configured(name='CCString',direction='response_format'):
    tree=dict(occurrence_id='field',java_class='com.ibm.il.dse.cc.format.'+name,attributes={'dataName':'Value'},children=[],
        decorators=[dict(occurrence_id='one',java_class='example.ValueDecorator',attributes={'mode':'one'}),
                    dict(occurrence_id='two',java_class='example.ValueDecorator',attributes={'mode':'two'}),
                    dict(occurrence_id='nil',java_class='com.ibm.il.dse.cc.decorator.NilDecorator',attributes={})])
    extra=source('value','package example;public class ValueDecorator extends com.ibm.dse.base.FormatDecoratorHolder {}')
    return dict(kind=direction,effective_configuration=tree,referenced_definitions=[]),[*original_sources(),extra]


def test_real_original_forward_reverse_attribute_scope_and_table_conditional_hooks():
    config,sources=configured()
    chain=configured_chains(config,sources)[0]
    assert [item.get('occurrence_id') for item in chain['operations']]==[None,'one','two','nil']
    assert chain['operations'][-1]['kind']=='xml_attributes'
    assert 'formatXmlAttributes(context, value)' in chain['source_hooks']['render']['excerpt']
    config['kind']='request_unformat'
    chain=configured_chains(config,sources)[0]
    assert [item.get('occurrence_id') for item in chain['operations']]==['two','one',None]
    assert chain['inactive_decorators']==['nil']
    config,sources=configured('CCTableFormat')
    chain=configured_chains(config,sources)[0]
    assert 'if (rs.next())' in chain['source_hooks']['format']['excerpt']
    assert 'if (key == null)' in chain['source_hooks']['format']['excerpt']
    config['kind']='request_unformat'
    assert [item['kind'] for item in configured_chains(config,sources)[0]['operations']]==['basic']
    config,sources=configured('CCBoolean')
    assert configured_chains(config,sources)[0]['inactive_decorators']==['one','two','nil']


def test_chain_identity_distinguishes_order_settings_and_direction():
    config,sources=configured();first=configured_chains(config,sources)[0]['class_name']
    config['effective_configuration']['decorators'].reverse()
    assert configured_chains(config,sources)[0]['class_name']!=first
    config,sources=configured();config['effective_configuration']['attributes']['dataName']='Other'
    assert configured_chains(config,sources)[0]['class_name']!=first
    config['kind']='request_unformat'
    assert configured_chains(config,sources)[0]['class_name']!=first


def test_unproven_original_loop_or_unknown_decorator_fails_closed():
    config,sources=configured(direction='request_unformat')
    sources=[dict(item,content=item['content'].replace('i--','i += 0')) for item in sources]
    with pytest.raises(ValueError,match='order is not proven'):configured_chains(config,sources)
    config,sources=configured();config['effective_configuration']['decorators'][0]['java_class']='absent.Unknown'
    with pytest.raises(ValueError,match='scope lacks'):configured_chains(config,sources)


def native_chain_case():
    path='src/main/java/nativecode/FormatChainExample.java';mapper='src/main/java/nativecode/Mapper.java'
    body='public String format(String input) { String value = new nativecode.Basic().format(input); value = new nativecode.First().add(value); value = new nativecode.Second().add(value); return value; }'
    text='package nativecode;public class FormatChainExample { '+body+' }'
    files={path:text,mapper:'package nativecode;public class Mapper { public String render(String input){ return new nativecode.FormatChainExample().format(input); } }'}
    request=dict(native_package='nativecode',format_chains=[dict(occurrence_id='field',class_name='FormatChainExample')])
    bundle=SimpleNamespace(files=[SimpleNamespace(path=p,content=t) for p,t in files.items()])
    return bundle,request


def test_basic_requests_retain_collector_scoping_without_post_filtering_facts():
    items=[dict(id='call',kind='call',excerpt='applyDecorators(result)'),
        dict(id='branch',kind='branch',excerpt='if(rs.next()){result = applyDecorators(result);}'),
        dict(id='db',kind='call',excerpt='rs.getString(1)')]
    delegated=[dict(checklist_id='call',owner='complete_configured_format')]
    request=dict(parser_checklist=items[1:],composition_obligations=delegated)
    plan=SimpleNamespace(components={'basic':SimpleNamespace(roles=['format_leaf'])})
    attach_format_chains(request,plan,SimpleNamespace(members=['basic']),{})
    assert [item['checklist_id'] for item in request['composition_obligations']]==['call']
    assert [item['id'] for item in request['parser_checklist']]==['branch','db']


@pytest.fixture(scope='module')
def chain_tool():
    from runtime.java_toolchain import java_scope,run_java
    from models.pipeline_configuration import PipelineConfiguration
    from tools.maven_dependency_tools.command import maven_executable
    from tools.behavior_verification.java_tool import default_tool_path
    with java_scope(PipelineConfiguration(java_version=25)):
        result=run_java([maven_executable(),'-q','--offline','-f',str(Path(__file__).resolve().parents[1]/'behavior-verification-java/pom.xml'),'package'],
            capture_output=True,text=True,timeout=120,check=False)
        assert result.returncode==0,result.stdout+result.stderr
        yield default_tool_path()


def test_real_deterministic_collector_omits_chaining_only_in_basic_scope(chain_tool):
    from tools.behavior_verification.boundaries import build_boundary_report
    from test_behavior_verification_boundaries import unit,prepared,first
    sources=[source('format','''package example;
import com.ibm.dse.base.Context;import java.util.*;
public class Format {
 private final List<FormatDecoratorHolder> decorators = new ArrayList<>();
 public String format(Context context) {
  String value = context.getValueAt("VALUE").toString();
  value = applyDecorators(value);
  return value;
 }
 public void unformat(String value, Context context) { context.setValueAt("VALUE", removeDecorators(value)); }
 public void addDecorator(FormatDecoratorHolder decorator) { decorators.add(decorator); }
 protected String applyDecorators(String value) { for(FormatDecoratorHolder decorator:decorators) value=decorator.addDecoration(value);return value; }
 protected String removeDecorators(String value) { for(int i=decorators.size()-1;i>=0;i--)value=decorators.get(i).removeDecoration(value);return value; }
}'''),source('holder','''package example;public class FormatDecoratorHolder {
 public String addDecoration(String value){return value;}public String removeDecoration(String value){return value;}
}'''),source('decorator','''package example;public class Decorator extends FormatDecoratorHolder {
 public String addDecoration(String value){if(value==null)throw new IllegalArgumentException("missing value");return "["+value+"]";}
}'''),source('context','''package com.ibm.dse.base;public class Context {
 public Object getValueAt(String key){return null;}public void setValueAt(String key,Object value){}
}''')]
    boundary=first(build_boundary_report(prepared(unit('response_format','example.Format',sources)),tool_jar=chain_tool))
    full=boundary['parser_checklist'];basic=boundary['basic_parser_checklist']
    assert full['status']==basic['status']=='extracted',boundary
    assert {item['id'] for item in basic['items']} < {item['id'] for item in full['items']}
    assert any('applyDecorators' in item['excerpt'] and item['kind']=='call' for item in full['items'])
    assert not any('applyDecorators' in item['excerpt'] and item['kind']=='call' for item in basic['items'])
    assert any('getValueAt' in item['excerpt'] for item in basic['items'])
    assert any('missing value' in item['excerpt'] for item in basic['items'] if item['source_identity']=='decorator')


def test_mapping_receives_scope_and_reserves_the_complete_chain_instruction():
    from runtime.component_conversion.format_chains import checklist_chain_context
    from runtime.behavior_conversion.metadata_checklist_batches import build_request,EvidenceTooLarge
    from runtime.behavior_conversion.metadata_checklist_evidence import source_catalog
    from agents.behavior_conversion.metadata_checklist import MAPPING,CHAIN_MAPPING
    from models.pipeline_configuration import PipelineConfiguration
    from test_metadata_checklist import items,ORIGINAL,CODE,PATH
    config,sources=configured()
    payload=dict(format_chain_policy='configured-format-chains-v1',format_chains=configured_chains(config,sources))
    context=checklist_chain_context(payload)
    assert context['fact_scope']=='complete_unit' and 'source_hooks' not in context['format_chains'][0]
    assert checklist_chain_context(dict(payload,basic_format_behavior={'roles':['format_leaf']}))['fact_scope']=='basic_element'
    assert checklist_chain_context({})=={}
    from runtime.behavior_conversion.metadata_semantics import semantic_request
    semantic=semantic_request(payload,SimpleNamespace(files=[]),dict(apis=[]))
    assert 'format_chains' not in semantic
    catalog=source_catalog(dict(sources=[source('original',ORIGINAL)]),{PATH:CODE},{})
    values={item['id']:item for item in items(1)}
    profile=PipelineConfiguration()
    _,encoded=build_request(list(values),values,catalog,profile,'revision','production',context=context)
    size=len(encoded)+len(MAPPING)+len(CHAIN_MAPPING)
    assert size<=profile.metadata_checklist_request_chars-profile.metadata_checklist_response_chars
    bounded=profile.model_copy(update={'metadata_checklist_request_chars':size+profile.metadata_checklist_response_chars-1})
    with pytest.raises(EvidenceTooLarge):build_request(list(values),values,catalog,bounded,'revision','production',context=context)
