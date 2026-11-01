"""CF5 composes source-backed formats and compares complete original/native boundaries."""
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.native_format_component_bundle import NativeFormatComponentBundle
from runtime.component_conversion.requests import build_component_request
from runtime.component_conversion.formats import format_source_bindings,native_format_prerequisites
from runtime.component_conversion.format_verification import format_bundle,session_for
from runtime.component_conversion.scope import component_execution,require_component_task
from runtime.component_conversion.runner import convert_basic_components
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.component_identity import component_group
from tools.behavior_verification.boundaries import build_boundary_report
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.conversion_components import register_component_plan
from tools.state_store_tools.component_configuration import configuration_group,bind_configuration,verify_configuration
from test_component_graph import origin,operation,step,format_node
from test_behavior_verification_boundaries import boundary_tool
from test_typed_boundary_adapter import ROOT

XML='<Reply xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><Error xsi:nil="true"/></Reply>'
HELPER='package example;public class Helper{public String xml(){return '+json.dumps(XML)+';}}'
FORMAT='''package example;import com.ibm.dse.base.Context;public class SimpleFormat{
 public String format(Context context){return new Helper().xml();}
 public void unformat(String xml,Context context){}
}'''


@pytest.fixture
def format_case(tmp_path,boundary_tool,monkeypatch):
    tool=tmp_path/'analysis.jar';shutil.copy2(boundary_tool,tool)
    def analyze(preparation,**options): return build_boundary_report(preparation,tool_jar=tool,**options)
    monkeypatch.setattr('runtime.component_conversion.runner.build_boundary_report',analyze)
    monkeypatch.setattr('runtime.component_conversion.format_verification.default_tool_path',lambda:tool)
    monkeypatch.setattr('runtime.component_conversion.scope.validate_checkpoints',lambda *a:None)
    original=tmp_path/'original';original.mkdir()
    origins=[origin('example.Helper',text=HELPER),origin('example.SimpleFormat',['example.Helper'],FORMAT)]
    for item,text in origins:
        path=original/(item['fqcn'].rsplit('.',1)[-1]+'.java');path.write_text(text,encoding='utf-8',newline='\n');item['source_file']=str(path)
    units=[]
    for identity,kind in [('request','request_unformat'),('response','response_format')]:
        body=format_node('SimpleFormat',identity+'-body','example.SimpleFormat');body['attributes']={'dataName':'Reply'}
        tree=format_node('fmtDef',identity);tree['children']=[body]
        unit=step(identity);unit.update(kind=kind,logical_id=identity,source_definition_id=identity,occurrence_id=kind,
            consumers=['XML/Flow'],effective_configuration=tree,configuration_xml='<fmtDef id="'+identity+'"><SimpleFormat dataName="Reply"/></fmtDef>')
        units.append(unit)
    item=operation(units,origins)
    context=(ROOT/'com/ibm/dse/base/Context.java').read_text()
    # Framework Context is provided completely to the original harness, not generated as a native runtime.
    for unit in units: unit['sources'].append(dict(identity='framework:Context',content=context,content_hash=hashlib.sha256(context.encode()).hexdigest()))
    preparation=dict(operations={'XML/Flow':item});plan=build_component_plan(preparation['operations'])
    preparation['component_plan']=plan.model_dump(mode='json');boundaries=analyze(preparation)
    assert boundaries['counts']['identified']==2,boundaries
    conn=get_connection(str(tmp_path/'state.db'));create_all_tables(conn);upsert_run(conn,run_id='cf5',run_mode='conversion')
    config=SimpleNamespace(run_id='cf5',source_root=str(original),output_root=str(tmp_path/'generated'))
    profile=PipelineConfiguration(source_root=str(original),java_version=25,conversion_strategy='behavior_units',scoped_native_mode='component_first_v1',max_agent_task_retries=1)
    yield conn,config,profile,preparation,plan,boundaries,{unit['unit_id']:unit for unit in units}
    conn.close()


def request_for(case,identity='response'):
    _,_,profile,_,plan,boundaries,units=case;group=component_group(plan,plan.unit_roots[identity])
    request,instruction=build_component_request(plan,group,boundaries,[],profile,units=units)
    return group,request,instruction


def candidate(request,*,dependencies=(),defect=False):
    key=next(iter(request['components']));package=request['native_package'];kind=request['kind']
    prefix=package.replace('.','/');evidence=[item['identity'] for item in request['sources']]+request.get('configuration_evidence_ids',[])
    mode='parameterized'
    if request['components'][key]['label']=='example.Helper':
        name='XmlValue';apis=['public String xml()'];body='public String xml(){return '+json.dumps(XML)+';}'
        assertion='assertEquals('+json.dumps(XML)+',new XmlValue().xml());'
    else:
        dep=next(item for item in request['prerequisite_components'] if item.get('contracts'))
        target=next(iter(dep['contracts'].values()))['apis'][0]['type_name']
        if kind!='format_composition':
            name='FormatLogic';apis=['public String format()','public void unformat(String xml)']
            body='public String format(){return new '+target+'().xml();} public void unformat(String xml){}'
            assertion='assertEquals('+json.dumps(XML)+',new FormatLogic().format());new FormatLogic().unformat("<Reply/>");'
        else:
            mode='specialized';name='ReplyMapper' if request['configured_format']['kind']=='response_format' else 'RequestMapper'
            if name=='ReplyMapper':
                apis=['public String render()'];body='public String render(){return '+(json.dumps(XML.replace('xsi:','bad:').replace('xmlns:xsi','xmlns:bad')) if defect else 'new '+target+'().format()')+';}'
                assertion='assertNotNull(new ReplyMapper().render());'
            else:
                apis=['public void read(String xml)'];body='public void read(String xml){new '+target+'().unformat(xml);}'
                assertion='new RequestMapper().read("<Reply/>");'
    main_path='src/main/java/'+prefix+'/'+name+'.java';test_path='src/test/java/'+prefix+'/'+name+'Test.java'
    main='package '+package+';public class '+name+'{'+body+'}'
    test='package '+package+';import org.junit.jupiter.api.Test;import static org.junit.jupiter.api.Assertions.*;public class '+name+'Test{@Test public void sourceBehavior(){'+assertion+'}}'
    junit=next(item for item in request['known_dependencies'] if item['artifact_id']=='junit-jupiter')
    result=dict(contracts={key:dict(component_id=key,apis=[dict(type_name=package+'.'+name,method_signatures=apis)],
        source_entry_points=request['source_entry_points'][key],evidence_ids=evidence,dependencies=request['components'][key]['dependencies'],configuration_mode=mode)},
        files=[dict(path=main_path,content=main),dict(path=test_path,content=test)],dependencies=[junit],evidence_ids=evidence,
        coverage={identity:[test_path] for identity in request['requirements']})
    if kind=='format_composition':
        sources={path:text for dep in request['prerequisite_components'] for path,text in dep.get('sources',{}).items()}
        sources.update(dependencies);sources[main_path]=main
        location_path=next((path for path,text in sources.items() if 'public String xml()' in text),main_path)
        excerpt=(next((text[text.index('public String xml()'):text.rindex('}')] for text in sources.values() if 'public String xml()' in text),body))
        result.update(checklist_answers=dict(**request['verification_boundary'],responses=[dict(checklist_id=item['id'],status='implemented',
            locations=[dict(path=location_path,excerpt=excerpt)]) for item in request['parser_checklist']]),verification_binding=dict(
            owner_type=package+'.'+name,method_name='render' if name=='ReplyMapper' else 'read',
            arguments=[] if name=='ReplyMapper' else [dict(type_name='java.lang.String',source='xml')],output='result' if name=='ReplyMapper' else 'none'))
    else:
        result['checklist_implementations']={item['id']:[dict(path=main_path,excerpt=body)] for item in request['parser_checklist']}
    return result


def test_format_requests_preserve_direction_tree_references_and_original_unit_ids(format_case):
    _,config,profile,preparation,plan,_,units=format_case
    group,a,instruction=request_for(format_case);_,b,_=request_for(format_case,'request')
    assert a['kind']=='format_composition' and a['configured_format']['kind']=='response_format'
    assert b['configured_format']['kind']=='request_unformat' and a['native_package']!=b['native_package']
    assert a['configured_format']['effective_configuration']==units['response']['effective_configuration']
    assert a['sources'][0]['content']==FORMAT and HELPER not in json.dumps(a)
    assert len(native_format_prerequisites(plan,group))==1
    assert 'checklist_answers' in instruction and 'XML interpreter' in instruction
    assert format_source_bindings(plan,group,units)
    assert len(plan.unit_roots)==2


def test_format_scope_rejects_changed_structure_or_disabled_capability(format_case):
    conn,config,profile,preparation,_,_,_=format_case;group,request,_=request_for(format_case)
    with component_execution(conn,config,profile,None,preparation),pytest.raises(ValueError,match='deferred'):
        require_component_task(conn,config,profile,group.group_id,request)
    changed=deepcopy(request);changed['configured_format']['effective_configuration']['children'][0]['attributes']['dataName']='Wrong'
    with component_execution(conn,config,profile,None,preparation,include_formats=True),pytest.raises(ValueError,match='structure'):
        require_component_task(conn,config,profile,group.group_id,changed)


def test_configuration_is_not_generated_and_cannot_bind_missing_native_prerequisites(format_case):
    conn,config,profile,_,plan,_,_=format_case;register_component_plan(conn,config.run_id,plan,profile)
    group=next(group for group in plan.groups if configuration_group(plan,group) and group.dependencies)
    with pytest.raises(ValueError,match='prerequisite'):
        bind_configuration(conn,config.run_id,plan,group,profile)
    with pytest.raises(ValueError,match='not current'):
        verify_configuration(conn,config.run_id,plan,group)


def fixture_tree(request):
    """Provide actual native prerequisites for isolated parser/boundary verification tests."""
    prefix='com/company/generated/fixture/'
    helper='package com.company.generated.fixture;public class XmlValue{public String xml(){return '+json.dumps(XML)+';}}'
    logic='package com.company.generated.fixture;public class FormatLogic{public String format(){return new XmlValue().xml();}public void unformat(String xml){}}'
    files={'src/main/java/'+prefix+'XmlValue.java':helper,'src/main/java/'+prefix+'FormatLogic.java':logic}
    request=deepcopy(request);request['prerequisite_components']=[dict(contracts={'impl':dict(apis=[dict(type_name='com.company.generated.fixture.FormatLogic')])},sources=files)]
    return request,files


@pytest.mark.parametrize('identity',['request','response'])
def test_format_static_and_actual_boundary_comparison(format_case,tmp_path,identity):
    _,config,profile,_,_,boundaries,units=format_case;_,request,_=request_for(format_case,identity)
    request,files=fixture_tree(request);native=NativeFormatComponentBundle.model_validate(candidate(request,dependencies=files))
    bundle=format_bundle(native,request,files)
    session=session_for(config,profile,units[identity],boundaries['boundaries'][identity]);session.static(bundle)
    from tools.behavior_verification.boundary_verification import verify_boundary
    from tools.behavior_verification.controlled_inputs import generate_boundary_cases
    from models.boundary_harness_binding import BoundaryHarnessBinding
    binding=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',native_entry=native.verification_binding,
        sources=[dict(path=file.path,content=file.content) for file in bundle.files if file.path.startswith('src/main/java/')])
    report=verify_boundary(units[identity],session.boundary,BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),
        binding,generate_boundary_cases(units[identity],session.boundary),tmp_path/'comparison',tool=session.tool,candidate_label='deterministic_composed_fixture')
    assert report.status=='matched_observed_cases',report.model_dump_json(indent=2)
    assert not report.coverage.get('unresolved_edges'),report.model_dump_json(indent=2)
    assert not any(item['unexercised_outcomes'] for item in report.coverage.get('branches',[])),report.model_dump_json(indent=2)
    expected='native:com.company.generated.fixture.FormatLogic.'+('unformat(java.lang.String)' if identity=='request' else 'format()')
    assert any(probe['id']==expected for case in report.cases for probe in case['native']['probes'])


def test_prefix_defect_fails_actual_original_native_comparison(format_case,tmp_path):
    _,config,profile,_,_,boundaries,units=format_case;_,request,_=request_for(format_case)
    request,files=fixture_tree(request);native=NativeFormatComponentBundle.model_validate(candidate(request,dependencies=files,defect=True))
    bundle=format_bundle(native,request,files);session=session_for(config,profile,units['response'],boundaries['boundaries']['response'])
    session.static(bundle)
    from tools.behavior_verification.boundary_verification import verify_boundary
    from tools.behavior_verification.controlled_inputs import generate_boundary_cases
    from models.boundary_harness_binding import BoundaryHarnessBinding
    binding=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',native_entry=native.verification_binding,
        sources=[dict(path=file.path,content=file.content) for file in bundle.files if file.path.startswith('src/main/java/')])
    report=verify_boundary(units['response'],session.boundary,BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),
        binding,generate_boundary_cases(units['response'],session.boundary),tmp_path/'defect',tool=session.tool,candidate_label='deliberate_prefix_defect')
    assert report.status=='differences_found' and any(case['differences'] for case in report.cases),report.model_dump_json(indent=2)


def test_configuration_receipts_track_native_revision_changes_without_accepting_units(format_case):
    conn,config,profile,_,plan,_,_=format_case;register_component_plan(conn,config.run_id,plan,profile)
    for group in plan.groups:
        if all(plan.components[key].kind=='java_implementation' for key in group.members):
            # State-only fixture; real artifacts and boundary comparison are exercised by the Maven test.
            conn.execute("UPDATE conversion_component_heads SET status='component_validated',contract_revision=?,result_revision=? WHERE run_id=? AND group_id=?",
                ('contract-'+group.group_id,'result-'+group.group_id,config.run_id,group.group_id))
        elif configuration_group(plan,group): bind_configuration(conn,config.run_id,plan,group,profile)
    configured=[group for group in plan.groups if configuration_group(plan,group)]
    assert configured and all(verify_configuration(conn,config.run_id,plan,group) for group in configured)
    direct=next(group for group in configured if any(not configuration_group(plan,next(item for item in plan.groups if item.group_id==key)) for key in group.dependencies))
    dependency=direct.dependencies[0]
    conn.execute("UPDATE conversion_component_heads SET result_revision='changed' WHERE run_id=? AND group_id=?",(config.run_id,dependency))
    with pytest.raises(ValueError,match='revision changed'): verify_configuration(conn,config.run_id,plan,direct)
    bind_configuration(conn,config.run_id,plan,direct,profile)
    assert conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category IN ('unit','unit_verification','operation')").fetchone()[0]==0


def test_changed_tree_cannot_use_an_old_parser_boundary(format_case):
    _,_,profile,preparation,_,boundaries,units=format_case
    changed=deepcopy(preparation['operations']);unit=changed['XML/Flow']['units'][0]
    unit['effective_configuration']['children'][0]['attributes']['dataName']='Changed'
    plan=build_component_plan(changed);group=component_group(plan,plan.unit_roots[unit['unit_id']])
    with pytest.raises(ValueError,match='parser boundary'):
        build_component_request(plan,group,boundaries,[],profile,units={item['unit_id']:item for item in changed['XML/Flow']['units']})


def test_request_composition_preserves_actual_context_writes(format_case,tmp_path):
    from runtime.component_conversion.runner import build_boundary_report as analyze
    _,config,profile,preparation,_,_,_=format_case
    changed=deepcopy(preparation)
    text=FORMAT.replace('public void unformat(String xml,Context context){}','public void unformat(String xml,Context context){context.setValueAt("Seen",xml);}')
    origin_record=next(item for item in changed['operations']['XML/Flow']['behavior_request']['java_origins'] if item['fqcn']=='example.SimpleFormat')
    Path(origin_record['source_file']).write_text(text,encoding='utf-8',newline='\n');origin_record['source_hash']=hashlib.sha256(text.encode()).hexdigest()
    for unit in changed['operations']['XML/Flow']['units']:
        for source in unit['sources']:
            if source['identity']==origin_record['definition_id']: source.update(content=text,content_hash=origin_record['source_hash'])
    plan=build_component_plan(changed['operations']);boundaries=analyze(changed)
    units={unit['unit_id']:unit for unit in changed['operations']['XML/Flow']['units']};group=component_group(plan,plan.unit_roots['request'])
    request,_=build_component_request(plan,group,boundaries,[],profile,units=units);request,files=fixture_tree(request)
    for path in files:
        files[path]=files[path].replace('public void unformat(String xml){}','public String unformat(String xml){return xml;}')
    data=candidate(request,dependencies=files);package=request['native_package'];key=group.members[0]
    body='public Result read(String xml){return new Result(new com.company.generated.fixture.FormatLogic().unformat(xml));}'
    data['files'][0]['content']='package '+package+';public class RequestMapper{'+body+'public static class Result{private final String seen;public Result(String seen){this.seen=seen;}public String getSeen(){return seen;}}}'
    data['contracts'][key]['apis'][0]['method_signatures']=['public '+package+'.RequestMapper.Result read(String xml)']
    data['verification_binding']['context_writes']=[dict(context_key='Seen',getters=['getSeen'])]
    for answer in data['checklist_answers']['responses']: answer['locations']=[dict(path=data['files'][0]['path'],excerpt=body)]
    native=NativeFormatComponentBundle.model_validate(data);bundle=format_bundle(native,request,files)
    session=session_for(config,profile,units['request'],boundaries['boundaries']['request']);session.static(bundle)
    from tools.behavior_verification.boundary_verification import verify_boundary
    from tools.behavior_verification.controlled_inputs import generate_boundary_cases
    from models.boundary_harness_binding import BoundaryHarnessBinding
    binding=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',native_entry=native.verification_binding,
        sources=[dict(path=file.path,content=file.content) for file in bundle.files if file.path.startswith('src/main/java/')])
    report=verify_boundary(units['request'],session.boundary,BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),
        binding,generate_boundary_cases(units['request'],session.boundary),tmp_path/'writes',tool=session.tool,candidate_label='composed_request_state_fixture')
    assert report.status=='matched_observed_cases',report.model_dump_json(indent=2)
    assert all(case['native']['context']['Seen']==case['case']['input_xml'] for case in report.cases)


def test_real_maven_composition_compares_both_directions_and_reuses_without_models(format_case,tmp_path):
    from tests.runtime.test_scoped_native import actual_build
    from runtime.workspace_paths import run_report_path
    conn,config,profile,preparation,plan,_,_=format_case;calls=[]
    def model(instruction,encoded):
        request=json.loads(encoded);calls.append(request)
        return json.dumps(candidate(request))
    directory=tmp_path/'run'
    convert_basic_components(conn,config,profile,directory,preparation,None,model_call=model,context_factory=actual_build,include_formats=True)
    report=json.loads(run_report_path(directory,'component-generation.json').read_text())
    assert report['component_validated']==4,report
    assert len(calls)==4 and len([item for item in calls if item['kind']=='format_composition'])==2
    assert any(item['status']=='configuration_bound' for item in report['groups'].values())
    assert report['accepted_units']==report['accepted_operations']==0
    convert_basic_components(conn,config,profile,directory,preparation,None,model_call=lambda *a:pytest.fail('Unchanged formats must reuse'),context_factory=actual_build,include_formats=True)
    report=json.loads(run_report_path(directory,'component-generation.json').read_text())
    assert report['reused_components']==4,report
