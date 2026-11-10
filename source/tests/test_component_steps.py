"""CF4 isolates occurrences and connects validated native prerequisites without accepting units."""
import json
import shutil
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.native_component_bundle import NativeComponentBundle
from models.pipeline_configuration import PipelineConfiguration
from runtime.component_conversion.requests import build_component_request
from runtime.component_conversion.steps import source_bindings, configured_step, validate_step_candidate, default_step_mappings
from runtime.component_conversion.runner import convert_basic_components
from runtime.component_conversion.scope import component_execution, require_component_task
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.component_identity import component_group
from tools.behavior_verification.boundaries import build_boundary_report
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.runs import upsert_run
from test_component_graph import origin, step, operation
from test_behavior_verification_boundaries import boundary_tool

WORK = '''package example;
public class Work {
 private int increment;
 public void initializeFrom(java.util.Map<String,String> attributes) { increment=Integer.parseInt(attributes.get("increment")); }
 public int execute() { return new Helper().apply(5,increment); }
}'''
HELPER = 'package example; public class Helper { public int apply(int value,int increment){ return value+increment; } }'


@pytest.fixture
def steps_case(tmp_path, boundary_tool, monkeypatch):
    pinned_tool=tmp_path/'analysis-tool.jar'
    shutil.copy2(boundary_tool,pinned_tool)
    def analyze(preparation,**options):
        return build_boundary_report(preparation,tool_jar=pinned_tool,**options)
    monkeypatch.setattr('runtime.component_conversion.runner.build_boundary_report',analyze)
    source = tmp_path/'original'; source.mkdir()
    originals = [origin('example.Work',['example.Helper'],WORK), origin('example.Helper',text=HELPER), origin('example.Unrelated')]
    for metadata, text in originals:
        path=source/(metadata['fqcn'].rsplit('.',1)[-1]+'.java')
        path.write_text(text,encoding='utf-8',newline='\n'); metadata['source_file']=str(path)
    units=[step('first','1'),step('second','2')]
    for index,unit in enumerate(units):
        unit['consumers']=['SME/Flow']
        unit['effective_configuration']['attributes'].update(id='Repeat',increment=str(index+1))
        unit['effective_configuration']['routes']={'on0Do':'second' if index==0 else 'end','onOtherDo':None}
        unit['effective_configuration']['return_body_switches']={'onOtherReturn':'ErrorFmt'} if index else {}
        unit['configuration_xml']='<opStep id="Repeat" increment="'+str(index+1)+'"/>'
    operations={'SME/Flow':operation(units,originals)}
    plan=build_component_plan(operations)
    preparation=dict(operations=operations,component_plan=plan.model_dump(mode='json'))
    boundaries=analyze(preparation)
    assert boundaries['counts']['identified']==2,boundaries
    conn=get_connection(str(tmp_path/'state.db')); create_all_tables(conn)
    config=SimpleNamespace(run_id='cf4',source_root=str(source),output_root=str(tmp_path/'generated'))
    upsert_run(conn,run_id='cf4',run_mode='conversion')
    profile=PipelineConfiguration(source_root=str(source),java_version=25,conversion_strategy='behavior_units',
        scoped_native_mode='component_first_v1',max_agent_task_retries=1)
    # A source/parser fixture, not an imported Composer vault or original/native comparison.
    monkeypatch.setattr('runtime.component_conversion.scope.validate_checkpoints',lambda *a:None)
    yield conn,config,profile,preparation,plan,boundaries,{unit['unit_id']:unit for unit in units}
    conn.close()


def root_request(case, identity='first', *, plan=None, units=None):
    _,_,profile,_,original,boundaries,current=case
    plan=plan or original; units=units or current
    group=component_group(plan,plan.unit_roots[identity])
    request,instruction=build_component_request(plan,group,boundaries,[],profile,units=units)
    return group,request,instruction


def test_repeated_steps_keep_own_configuration_routes_and_implementation_evidence(steps_case):
    first,a,instruction=root_request(steps_case)
    second,b,_=root_request(steps_case,'second')
    assert a['kind']==b['kind']=='configured_step' and a['native_package']!=b['native_package']
    assert a['configured_unit']['logical_id']==b['configured_unit']['logical_id']=='Repeat'
    assert a['configured_unit']['effective_configuration']['attributes']['increment']=='1'
    assert b['configured_unit']['effective_configuration']['attributes']['increment']=='2'
    assert a['configured_unit']['effective_configuration']['routes']['on0Do']=='second'
    assert b['configured_unit']['effective_configuration']['routes']['on0Do']=='end'
    assert b['configured_unit']['effective_configuration']['return_body_switches']=={'onOtherReturn':'ErrorFmt'}
    assert [item['content'] for item in a['sources']]==[WORK]
    assert 'example.Unrelated' not in json.dumps(a) and HELPER not in json.dumps(a)
    assert a['configured_unit']['occurrence_id']=='first' and b['configured_unit']['occurrence_id']=='second'
    assert 'do not choose the next step' in instruction
    plan=steps_case[4]
    assert source_bindings(plan,first)[first.members[0]]==source_bindings(plan,second)[second.members[0]]


def test_step_implementation_request_is_parameterized_and_contains_no_occurrence(steps_case):
    _,_,profile,_,plan,boundaries,_=steps_case
    key=next(key for key,node in plan.components.items() if node.label=='example.Work')
    request,instruction=build_component_request(plan,component_group(plan,key),boundaries,[],profile)
    assert request['kind']=='step_implementation' and 'configured_unit' not in request
    assert request['sources'][0]['content']==WORK
    assert 'parameter' in instruction and 'enclosing operation' in instruction


def test_analysis_classpath_identity_reaches_component_request_and_shared_reuse(steps_case):
    from runtime.component_conversion.shared_identity import request_identity
    _,_,profile,_,plan,boundaries,units=steps_case
    boundaries=deepcopy(boundaries)
    boundaries['analysis_classpath_hash']='verified-order-and-bytes'
    group=component_group(plan,plan.unit_roots['first'])
    request,_=build_component_request(plan,group,boundaries,[],profile,units=units)
    assert request['analysis_classpath_hash']=='verified-order-and-bytes'
    first=request_identity(request,profile)
    request['analysis_classpath_hash']='changed-order-or-bytes'
    assert request_identity(request,profile)!=first


def test_saved_step_specific_binding_reaches_component_request_without_impl_class(steps_case):
    _,_,profile,preparation,_,_,_=steps_case
    operations=deepcopy(preparation['operations'])
    for unit in operations['SME/Flow']['units']:
        configuration=unit['effective_configuration']
        configuration['attributes'].pop('implClass')
        configuration['attributes']['id']='OperationFailed'
        configuration.update(resolved_implementation='example.Work',implementation_mapping_key='OperationFailed')
    plan=build_component_plan(operations)
    mappings=default_step_mappings(plan)
    assert mappings=={'SME/Flow':{'OperationFailed':'example.Work'}}
    boundaries=build_boundary_report(dict(operations=operations),mappings=mappings)
    assert boundaries['counts']['identified']==2,boundaries
    units={unit['unit_id']:unit for unit in operations['SME/Flow']['units']}
    group=component_group(plan,plan.unit_roots['first'])
    request,_=build_component_request(plan,group,boundaries,[],profile,units=units)
    assert request['configured_unit']['resolved_implementation']=='example.Work'
    assert 'example.Work.execute()' in json.dumps(request['source_entry_points'])
    assert 'implClass' not in request['configured_unit']['effective_configuration']['attributes']


def test_complex_call_uses_only_its_qualified_contract_and_external_resource_evidence(steps_case):
    _,_,_,preparation,_,_,units=steps_case
    changed=deepcopy(preparation['operations']); current=deepcopy(units)
    call=dict(occurrence_id='first',callee='SME/POB1Op',service_contract=dict(fingerprint='saved-contract',
        method='POST',path='/native/sme/pob1',base_url_property='targets.pob1.base-url',source_channel='XML'))
    current['first']['operation_calls']=[call]
    current['first']['service_connections']=[dict(connection_id='pool',service_id='jdbcBank',channel='SME',issues=[])]
    changed['SME/Flow']['units']=[current['first'],current['second']]
    plan=build_component_plan(changed)
    group,request,_=root_request(steps_case,plan=plan,units=current)
    assert request['operation_calls']==[call]
    assert request['service_connections'][0]['service_id']=='jdbcBank'
    assert request['configured_unit']['consumers']==['SME/Flow']
    assert len([target for target in group.dependencies if any(plan.components[key].kind=='operation_contract'
        for key in next(item for item in plan.groups if item.group_id==target).members)])==1
    current['first']['operation_calls'][0]['service_contract'].pop('path')
    with pytest.raises(ValueError,match='native operation contract'):
        root_request(steps_case,plan=build_component_plan({'SME/Flow':dict(changed['SME/Flow'],units=list(current.values()))}),units=current)


def test_scope_rejects_another_occurrences_parameters_and_legacy_basic_only_scope(steps_case):
    conn,config,profile,preparation,plan,_,_=steps_case
    group,request,_=root_request(steps_case)
    with component_execution(conn,config,profile,None,preparation),pytest.raises(ValueError,match='deferred'):
        require_component_task(conn,config,profile,group.group_id,request)
    changed=deepcopy(request); changed['configured_unit']['effective_configuration']['attributes']['increment']='2'
    with component_execution(conn,config,profile,None,preparation,include_steps=True),pytest.raises(ValueError,match='occurrence'):
        require_component_task(conn,config,profile,group.group_id,changed)


def test_missing_native_prerequisite_blocks_step_generation(steps_case,tmp_path):
    conn,config,profile,preparation,plan,_,_=steps_case
    calls=[]
    def model(instruction,encoded):
        request=json.loads(encoded); calls.append(request['kind'])
        raise ValueError('Deliberately unavailable helper candidate')
    convert_basic_components(conn,config,profile,tmp_path/'run',preparation,None,model_call=model,include_steps=True)
    from runtime.workspace_paths import run_report_path
    report=json.loads(run_report_path(tmp_path/'run','component-generation.json').read_text())
    assert calls==['basic_component']
    for root in plan.unit_roots.values():
        assert report['groups'][component_group(plan,root).group_id]['status']=='incomplete'
    assert report['accepted_units']==report['accepted_operations']==0


def candidate(request):
    """A deterministic, source-derived native candidate fixture; not live AI conversion."""
    key=next(iter(request['components'])); node=request['components'][key]
    package=request['native_package']; prefix=package.replace('.','/')
    evidence=[item['identity'] for item in request['sources']]+request.get('configuration_evidence_ids',[])
    mode='parameterized'; method='public int apply(int value, int increment)'
    if node['label']=='example.Helper':
        name='Arithmetic'; body='public int apply(int value,int increment){return value+increment;}'
        assertion='assertEquals(7,new Arithmetic().apply(5,2));'
    else:
        dependency=next(item for item in request['prerequisite_components'] if item.get('contracts'))
        dependency_type=next(iter(dependency['contracts'].values()))['apis'][0]['type_name']
        if request['kind']=='step_implementation':
            name='Work'; method='public int execute(int increment)'
            body='public int execute(int increment){return new '+dependency_type+'().apply(5,increment);}'
            assertion='assertEquals(6,new Work().execute(1));assertEquals(7,new Work().execute(2));'
        else:
            mode='specialized'; name='ConfiguredStep'; method='public int execute()'
            increment=request['configured_unit']['effective_configuration']['attributes']['increment']
            body='public int execute(){return new '+dependency_type+'().execute('+increment+');}'
            assertion='assertEquals('+str(5+int(increment))+',new ConfiguredStep().execute());'
    main_path='src/main/java/'+prefix+'/'+name+'.java'; test_path='src/test/java/'+prefix+'/'+name+'Test.java'
    main='package '+package+';public class '+name+'{'+body+'}'
    test='package '+package+';import org.junit.jupiter.api.Test;import static org.junit.jupiter.api.Assertions.*;public class '+name+'Test{@Test public void keepsOutcome(){'+assertion+'}}'
    junit=next(item for item in request['known_dependencies'] if item['artifact_id']=='junit-jupiter')
    return dict(contracts={key:dict(component_id=key,apis=[dict(type_name=package+'.'+name,method_signatures=[method])],
        source_entry_points=request['source_entry_points'][key],dependencies=node['dependencies'],evidence_ids=evidence,configuration_mode=mode)},
        files=[dict(path=main_path,content=main),dict(path=test_path,content=test)],dependencies=[junit],evidence_ids=evidence,
        coverage={identity:[test_path] for identity in request['requirements']},
        checklist_implementations={item['id']:[dict(path=main_path,excerpt=main)] for item in request['parser_checklist']})


def test_real_maven_steps_call_validated_prerequisites_and_resume_without_models(steps_case,tmp_path):
    from tests.runtime.test_scoped_native import actual_build
    from runtime.workspace_paths import run_report_path
    conn,config,profile,preparation,plan,_,_=steps_case
    calls=[]
    def model(instruction,encoded):
        request=json.loads(encoded); calls.append(request)
        return json.dumps(candidate(request))
    directory=tmp_path/'run'
    convert_basic_components(conn,config,profile,directory,preparation,None,model_call=model,context_factory=actual_build,include_steps=True)
    report=json.loads(run_report_path(directory,'component-generation.json').read_text())
    assert report['component_validated']==4,report
    configured=[item for item in calls if item['kind']=='configured_step']
    assert len(calls)==4 and len(configured)==2
    assert {item['configured_unit']['occurrence_id'] for item in configured}=={'first','second'}
    for item in configured:
        assert len(item['prerequisite_components'])==1
        assert all('src/test/' not in path for dep in item['prerequisite_components'] for path in dep.get('sources',{}))
        assert len(item['sources'])==1 and item['sources'][0]['content']==WORK
    convert_basic_components(conn,config,profile,directory,preparation,None,context_factory=actual_build,include_steps=True,
        model_call=lambda *a:pytest.fail('Unchanged configured steps must reuse'))
    report=json.loads(run_report_path(directory,'component-generation.json').read_text())
    assert report['reused_components']==4 and report['accepted_units']==report['accepted_operations']==0
    assert conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category IN ('unit','unit_verification','operation')").fetchone()[0]==0


def test_complex_step_rejects_canned_success_without_native_transport(steps_case):
    _,request,_=root_request(steps_case)
    request['configured_unit']['operation_calls']=[dict(service_contract=dict(path='/native/target'))]
    data=candidate(dict(request,prerequisite_components=[dict(contracts={'impl':dict(apis=[dict(type_name='com.company.generated.Work')])})]))
    with pytest.raises(ValueError,match='native HTTP transport'):
        validate_step_candidate(NativeComponentBundle.model_validate(data),request,{})
    contract=next(iter(data['contracts'].values()));contract['apis'][0]['method_signatures']=['public boolean execute()']
    with pytest.raises(ValueError,match='int execute'):
        validate_step_candidate(NativeComponentBundle.model_validate(data),request,{})


def test_default_step_mapping_uses_the_qualified_plan_for_parser_and_source(steps_case):
    _,_,profile,preparation,_,_,_=steps_case
    operations=deepcopy(preparation['operations'])
    for unit in operations['SME/Flow']['units']:
        unit['effective_configuration']['attributes'].pop('implClass')
    plan=build_component_plan(operations,step_mappings={'SME/Flow':'example.Work'})
    mappings=default_step_mappings(plan)
    assert mappings=={'SME/Flow':{'opStep':'example.Work'}}
    boundaries=build_boundary_report(dict(operations=operations),mappings=mappings)
    assert boundaries['counts']['identified']==2,boundaries
    units={unit['unit_id']:unit for unit in operations['SME/Flow']['units']}
    group=component_group(plan,plan.unit_roots['first'])
    request,_=build_component_request(plan,group,boundaries,[],profile,units=units)
    assert request['sources'][0]['content']==WORK
    assert request['configured_unit']['resolved_implementation']=='example.Work'
    assert 'implClass' not in request['configured_unit']['effective_configuration']['attributes']


def test_changed_operation_contract_is_checked_before_a_configured_task(steps_case,monkeypatch):
    conn,config,profile,preparation,_,_,units=steps_case
    operations=deepcopy(preparation['operations']); units=deepcopy(units)
    units['first']['operation_calls']=[dict(occurrence_id='first',callee='SME/Target',service_contract=dict(
        fingerprint='old',method='POST',path='/target',base_url_property='target.url'))]
    operations['SME/Flow']['units']=list(units.values())
    plan=build_component_plan(operations)
    group,request,_=root_request(steps_case,plan=plan,units=units)
    changed=dict(operations=operations,component_plan=plan.model_dump(mode='json'))
    def stale(*a,**k): raise ValueError('Target operation contract changed')
    monkeypatch.setattr('runtime.behavior_conversion.operation_calls.verify_operation_contracts',stale)
    with component_execution(conn,config,profile,None,changed,include_steps=True),pytest.raises(ValueError,match='contract changed'):
        require_component_task(conn,config,profile,group.group_id,request)


@pytest.mark.parametrize('signature,accepted',[
    ('/* before */ @Deprecated /* between */ public int execute()',True),
    ('@Description("int execute(") public boolean execute()',False),
    ('public Integer execute()',False)])
def test_integer_contract_uses_declarations_not_comment_or_annotation_text(signature,accepted):
    bundle=NativeComponentBundle.model_validate(dict(contracts={'step':dict(component_id='step',
        apis=[dict(type_name='com.company.generated.Step',method_signatures=[signature])],
        source_entry_points=['execute'],evidence_ids=['source'],configuration_mode='specialized')},
        files=[dict(path='src/main/java/com/company/generated/Step.java',content='package com.company.generated;public class Step{}')]))
    request=dict(configured_unit=dict(operation_calls=[]))
    if accepted: validate_step_candidate(bundle,request,{})
    else:
        with pytest.raises(ValueError,match='int execute'): validate_step_candidate(bundle,request,{})
