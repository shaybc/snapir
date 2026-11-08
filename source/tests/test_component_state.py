"""CF2 contracts/cache progress are immutable, source-bound and separate from unit acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import pytest
from models.native_component_contract import NativeComponentContract
from models.native_component_result import NativeComponentResult
from models.pipeline_configuration import PipelineConfiguration
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.component_identity import component_group,external_group
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools import component_records as records
from tools.state_store_tools.conversion_components import register_component_plan,register_component_contracts,save_component_results,reuse_component_result
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
from test_component_graph import origin,step,operation


def make_plan(folder,*,cycle=False,value='first',separate_helper=False):
    originals=[origin('example.Helper',['example.Work'] if cycle else []),origin('example.Work',['example.Helper']),origin('example.Other')]
    for item,text in originals:
        path=folder/(item['fqcn'].rsplit('.',1)[-1]+'.java')
        if not path.exists(): path.write_text(text)
        item.update(source_file=str(path),source_hash=file_digest(path))
    originals=[(item,Path(item['source_file']).read_text()) for item,_ in originals]
    units=[step(value=value),step('other-step',implementation='example.Other')]
    if separate_helper:
        # A configured implementation remains a conversion node instead of folded supporting evidence.
        units.append(step('helper-step',implementation='example.Helper'))
    return build_component_plan({'XML/Flow':operation(units,originals)})


def contract_for(plan,key,**changes):
    node=plan.components[key]
    name='C'+key[-12:]
    evidence=node.configuration.get('definition_id') or node.provenance.get('definition_id') or node.provenance.get('source_definition_id')
    data=dict(component_id=key,apis=[dict(type_name='com.company.generated.cf2.'+name,method_signatures=['public int apply(int value)'])],
              source_entry_points=['execute'],evidence_ids=[evidence],dependencies=node.dependencies)
    data.update(changes)
    return NativeComponentContract.model_validate(data)


def artifact(output,plan,key,contract,registered,*,version='one',real=False):
    root=output/(key[-12:]+'-'+version);root.mkdir(parents=True,exist_ok=True)
    initialize_managed_pom(str(root/'pom.xml'),'example','component',java_version=25)
    name=contract.apis[0].type_name.rsplit('.',1)[-1]
    main=root/('src/main/java/com/company/generated/cf2/'+name+'.java');main.parent.mkdir(parents=True,exist_ok=True)
    main.write_text('package com.company.generated.cf2; public class '+name+' { public int apply(int value){return value+1;} }')
    test=root/('src/test/java/com/company/generated/cf2/'+name+'Test.java');test.parent.mkdir(parents=True,exist_ok=True)
    test.write_text('package com.company.generated.cf2; public class '+name+'Test { public static void main(String[] args){'
        'if(new '+name+'().apply(2)!=3)throw new AssertionError();} }')
    compiled=root/'target/classes';compiled.mkdir(parents=True,exist_ok=True)
    if real:
        from runtime.java_toolchain import resolve_java_home
        home=Path(resolve_java_home(25))/'bin'
        subprocess.run([str(home/'javac.exe'),'--release','25','-d',str(compiled),str(main),str(test)],capture_output=True,text=True,check=True)
        subprocess.run([str(home/'java.exe'),'-cp',str(compiled),contract.apis[0].type_name+'Test'],capture_output=True,text=True,check=True)
    else:
        target=compiled/('com/company/generated/cf2/'+name+'.class');target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(b'explicit synthetic artifact for cache-state tests')
    files={p.relative_to(root).as_posix():file_digest(p) for p in root.rglob('*') if p.is_file()}
    report=dict(component_id=key,input_revision=registered['input_revision'],contract_revision=registered['contract_revision'],
        files=files,validation_scope='build_and_tests',validation=dict(build_passed=True,tests_passed=True,test_count=1,
        executed_test_classes=[contract.apis[0].type_name+'Test'],issues=[]),fixture='real JVM' if real else 'synthetic validator fixture, not live code acceptance')
    path=root/'validation.json';path.write_text(json.dumps(report))
    return NativeComponentResult(component_id=key,contract_revision=registered['contract_revision'],input_revision=registered['input_revision'],
        artifact_root=str(root),files=files,validation_report='validation.json',validation_report_hash=file_digest(path))


@pytest.fixture
def state(tmp_path):
    source=tmp_path/'original';source.mkdir()
    plan=make_plan(source)
    conn=get_connection(str(tmp_path/'state.db'));create_all_tables(conn)
    profile=PipelineConfiguration(java_version=25)
    output=tmp_path/'generated'
    yield conn,plan,profile,output,source
    conn.close()


@pytest.fixture
def dependency_state(state):
    conn,_,profile,output,source=state
    plan=make_plan(source,separate_helper=True)
    assert named(plan,'example.Helper') in plan.components[named(plan,'example.Work')].dependencies
    return conn,plan,profile,output,source


def register_all(conn,plan,profile,run='run'):
    registered={};contracts={}
    for group in plan.groups:
        if external_group(plan,group): continue
        values={key:contract_for(plan,key) for key in group.members}
        registered[group.group_id]=register_component_contracts(conn,run,plan,group.group_id,values,profile)
        contracts.update(values)
    return registered,contracts


def cache_all(conn,plan,profile,output,run='run'):
    registered,contracts=register_all(conn,plan,profile,run)
    saved={}
    for group in plan.groups:
        values={key:artifact(output,plan,key,contracts[key],registered[group.group_id]) for key in group.members}
        save_component_results(conn,run,plan,group.group_id,values,profile,output,validator=lambda *a:True)
        saved.update(values)
    return registered,contracts,saved


def named(plan,label):
    return next(key for key,node in plan.components.items() if node.label==label)


def test_unchanged_resume_revalidates_without_model_calls_or_unit_acceptance(state):
    conn,plan,profile,output,_=state
    _,_,saved=cache_all(conn,plan,profile,output)
    root=plan.unit_roots['step-1'];checks=[]
    def validate(contracts,results): checks.extend(results);return True
    result=reuse_component_result(conn,'run',plan,root,profile,output,validator=validate)
    assert result==saved[root] and len(checks)==2
    assert set(checks)=={root,named(plan,'example.Work')}
    assert [item['fqcn'] for item in plan.components[named(plan,'example.Work')].provenance['supporting_sources']]==['example.Helper']
    assert named(plan,'example.Other') not in checks
    assert conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category IN ('unit','unit_verification','operation')").fetchone()[0]==0
    assert conn.execute('SELECT count(*) FROM behavior_attempts').fetchone()[0]==0
    assert not result.unit_acceptance_enabled and result.behavioral_equivalence=='not_established'
    assert reuse_component_result(conn,'another-run',plan,root,profile,output,validator=validate) is None


def test_source_configuration_and_platform_changes_do_not_reuse_old_results(state):
    conn,plan,profile,output,source=state
    cache_all(conn,plan,profile,output)
    sibling=plan.unit_roots['other-step']
    (source/'Helper.java').write_text('package example; public class Helper { public int changed; }')
    with pytest.raises(ValueError,match='Original component source changed'):
        reuse_component_result(conn,'run',plan,plan.unit_roots['step-1'],profile,output,validator=lambda *a:True)
    assert records.head(conn,'run',component_group(plan,plan.unit_roots['step-1']).group_id)['status']=='stale'
    revised=make_plan(source)
    assert reuse_component_result(conn,'run',revised,revised.unit_roots['step-1'],profile,output,validator=lambda *a:True) is None
    assert reuse_component_result(conn,'run',revised,sibling,profile,output,validator=lambda *a:True) is not None
    configured=make_plan(source,value='different')
    assert configured.unit_roots['step-1']!=plan.unit_roots['step-1']
    assert reuse_component_result(conn,'run',configured,configured.unit_roots['step-1'],profile,output,validator=lambda *a:True) is None
    other_profile=profile.model_copy(update={'java_version':21})
    assert reuse_component_result(conn,'run',configured,sibling,other_profile,output,validator=lambda *a:True) is None


def test_dependency_invalidation_during_reuse_cannot_return_a_valid_result(dependency_state):
    conn,plan,profile,output,_=dependency_state
    cache_all(conn,plan,profile,output)
    root=plan.unit_roots['step-1']
    helper=component_group(plan,named(plan,'example.Helper'))
    def validate(contracts,results):
        if root in results:
            records.invalidate(conn,'run',[helper.group_id])
        return True
    with pytest.raises(ValueError,match='changed during reuse'):
        reuse_component_result(conn,'run',plan,root,profile,output,validator=validate)
    assert records.head(conn,'run',component_group(plan,root).group_id)['status']=='stale'


def test_contract_change_preserves_old_revision_and_stales_consumers_only(dependency_state):
    conn,plan,profile,output,_=dependency_state
    registered,_,_=cache_all(conn,plan,profile,output)
    key=named(plan,'example.Helper');group=component_group(plan,key)
    old=registered[group.group_id]['contract_revision']
    revised=register_component_contracts(conn,'run',plan,group.group_id,{key:contract_for(plan,key,runtime_inputs={'channel':'String'})},profile)
    assert revised['contract_revision']!=old
    assert records.read_record(conn,'run',group.group_id,'contract',old)['contracts'][key]['runtime_inputs']=={}
    assert reuse_component_result(conn,'run',plan,plan.unit_roots['step-1'],profile,output,validator=lambda *a:True) is None
    assert reuse_component_result(conn,'run',plan,plan.unit_roots['other-step'],profile,output,validator=lambda *a:True) is not None
    assert records.head(conn,'run',group.group_id)['status']=='contract_registered'


def test_implementation_revision_stales_consumers_and_keeps_unchanged_sibling(dependency_state):
    conn,plan,profile,output,_=dependency_state
    registered,contracts,_=cache_all(conn,plan,profile,output)
    key=named(plan,'example.Helper');group=component_group(plan,key)
    replacement=artifact(output,plan,key,contracts[key],registered[group.group_id],version='new-output')
    save_component_results(conn,'run',plan,group.group_id,{key:replacement},profile,output,validator=lambda *a:True)
    assert records.head(conn,'run',component_group(plan,plan.unit_roots['step-1']).group_id)['status']=='stale'
    assert reuse_component_result(conn,'run',plan,plan.unit_roots['other-step'],profile,output,validator=lambda *a:True) is not None


@pytest.mark.parametrize('change',['source','compiled','report','metadata','validator'])
def test_tampered_dependency_evidence_invalidates_all_consumers(dependency_state,change):
    conn,plan,profile,output,source=dependency_state
    _,_,saved=cache_all(conn,plan,profile,output)
    helper=named(plan,'example.Helper');group=component_group(plan,helper);result=saved[helper]
    if change=='source': (source/'Helper.java').write_text('changed source')
    elif change=='compiled':
        path=next(name for name in result.files if name.endswith('.class'));(Path(result.artifact_root)/path).write_bytes(b'changed')
    elif change=='report': (Path(result.artifact_root)/result.validation_report).write_text('{}')
    elif change=='metadata':
        conn.execute("UPDATE conversion_component_records SET record_json='{}' WHERE group_id=? AND category='result'",(group.group_id,));conn.commit()
    validator=(lambda *a:False) if change=='validator' else (lambda *a:True)
    with pytest.raises(ValueError): reuse_component_result(conn,'run',plan,plan.unit_roots['step-1'],profile,output,validator=validator)
    assert records.head(conn,'run',group.group_id)['status']=='stale'
    assert records.head(conn,'run',component_group(plan,plan.unit_roots['step-1']).group_id)['status']=='stale'
    assert records.head(conn,'run',component_group(plan,plan.unit_roots['other-step']).group_id)['status']=='component_validated'


def test_cycles_require_atomic_contract_and_result_sets(tmp_path):
    source=tmp_path/'original';source.mkdir();plan=make_plan(source,cycle=True,separate_helper=True)
    conn=get_connection(':memory:');create_all_tables(conn);profile=PipelineConfiguration()
    group=next(group for group in plan.groups if group.cyclic)
    assert set(group.members)=={named(plan,'example.Work'),named(plan,'example.Helper')}
    contracts={key:contract_for(plan,key) for key in group.members}
    with pytest.raises(ValueError,match='every component'):
        register_component_contracts(conn,'run',plan,group.group_id,{group.members[0]:contracts[group.members[0]]},profile)
    assert records.head(conn,'run',group.group_id)['contract_revision'] is None
    registered=register_component_contracts(conn,'run',plan,group.group_id,contracts,profile)
    output=tmp_path/'generated'
    results={key:artifact(output,plan,key,contracts[key],registered) for key in group.members}
    with pytest.raises(ValueError,match='every component'):
        save_component_results(conn,'run',plan,group.group_id,{group.members[0]:results[group.members[0]]},profile,output,validator=lambda *a:True)
    assert records.head(conn,'run',group.group_id)['result_revision'] is None
    save_component_results(conn,'run',plan,group.group_id,results,profile,output,validator=lambda *a:True)
    assert reuse_component_result(conn,'run',plan,group.members[0],profile,output,validator=lambda *a:True)==results[group.members[0]]
    conn.close()


def test_component_registration_does_not_commit_outer_transaction(state):
    conn,plan,profile,_,_=state
    records.initialize(conn);conn.commit()
    conn.execute('SAVEPOINT outer_work')
    register_component_plan(conn,'run',plan,profile)
    conn.execute('ROLLBACK TO SAVEPOINT outer_work');conn.execute('RELEASE SAVEPOINT outer_work')
    assert conn.execute('SELECT count(*) FROM conversion_component_heads').fetchone()[0]==0


def test_missing_build_or_escaping_paths_cannot_record_component_validation(dependency_state):
    conn,plan,profile,output,_=dependency_state
    registered,contracts=register_all(conn,plan,profile)
    key=named(plan,'example.Helper');group=component_group(plan,key)
    result=artifact(output,plan,key,contracts[key],registered[group.group_id])
    original=result.model_copy(deep=True)
    result.artifact_root=str(output.parent)
    result.files={'../escape':'x'}
    with pytest.raises(ValueError): save_component_results(conn,'run',plan,group.group_id,{key:result},profile,output,validator=lambda *a:True)
    result=original
    path=Path(result.artifact_root)/result.validation_report
    evidence=json.loads(path.read_text());evidence['validation']['test_count']=0;path.write_text(json.dumps(evidence))
    result.validation_report_hash=file_digest(path)
    with pytest.raises(ValueError,match='executed tests'):
        save_component_results(conn,'run',plan,group.group_id,{key:result},profile,output,validator=lambda *a:True)
    assert records.head(conn,'run',group.group_id)['result_revision'] is None


def test_real_jvm_artifact_can_be_revalidated_without_a_model(dependency_state):
    conn,plan,profile,output,_=dependency_state
    registered,contracts=register_all(conn,plan,profile)
    key=named(plan,'example.Helper');group=component_group(plan,key)
    result=artifact(output,plan,key,contracts[key],registered[group.group_id],real=True)
    def validate(current,results):
        from runtime.java_toolchain import resolve_java_home
        for component in results.values():
            subprocess.run([str(Path(resolve_java_home(25))/'bin/java.exe'),'-cp',str(Path(component.artifact_root)/'target/classes'),
                current[component.component_id].apis[0].type_name+'Test'],check=True,capture_output=True)
        return True
    save_component_results(conn,'run',plan,group.group_id,{key:result},profile,output,validator=validate)
    assert reuse_component_result(conn,'run',plan,key,profile,output,validator=validate)==result
