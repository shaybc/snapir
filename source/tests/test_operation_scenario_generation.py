"""Whole-operation preparation is generic, bounded, append-only and invoked during assembly."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest
from models.pipeline_configuration import PipelineConfiguration
from runtime.fixture_demo.scenario_generation import generate_operation_scenarios
from runtime.fixture_demo.artifact_paths import ARTIFACT_NAMES,demo_artifact,demo_workspace,migrate_demo_artifacts,saved_generation_proposal
from runtime.fixture_demo.scenario_evidence import collect_scenario_evidence
from runtime.fixture_demo.preparation import prepare_operation_demo
from runtime.fixture_demo.scenario_verification import verify_operation_scenario
from runtime.fixture_jdbc_tools.releases import file_hash
from test_fixture_demo import operation,free_port


def setup_operation(tmp_path):
    root,project,bank=operation(tmp_path)
    demo_artifact(project,'operation-demo-scenarios.json').unlink()
    source=project/'src/main/java/Example.java';source.parent.mkdir(parents=True)
    source.write_text('public class Example { /* SELECT Value FROM T WHERE Id = ? */ }')
    profile=PipelineConfiguration(model_provider='mock',max_agent_task_retries=2,
        test_preparation={'mode':'ai_shared_fixtures_v1'},format_comparison={'enabled':True,'max_cases':64})
    evidence,locations=collect_scenario_evidence(project,'INTERNET/Example')
    manifest=next(iter(locations))
    ref=lambda name:dict(bank=manifest,fixture_id=name,pointer='')
    proposal=dict(operation='INTERNET/Example',selected_scenario='whole-success',new_fixtures={
        'expected':dict(kind='xml',value='<Result>saved-value</Result>')},scenarios=[dict(
            scenario_id='whole-success',purpose='Reuse the saved request and JDBC data for the complete XML entry',
            input_xml=ref('request'),expected_xml=dict(bank='generated',fixture_id='expected',pointer=''),
            resources={'database':[ref('database')]},expected_resource_executions=1,
            expectation_citations=[dict(source_identity=evidence['native_sources'][0]['identity'],excerpt='SELECT Value FROM T WHERE Id = ?')])])
    return root,project,bank,profile,proposal


def test_automatic_generation_reuses_fixtures_and_reuses_unchanged_generation(tmp_path):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    original={p:file_hash(p) for p in bank.iterdir()};calls=[]
    def model(instruction,payload):
        calls.append(json.loads(payload));return json.dumps(proposal)
    result=generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=model)
    assert result['status']=='prepared',result
    definition=json.loads(demo_artifact(project,'operation-demo-scenarios.json').read_text())
    assert definition['scenarios'][0]['input_xml']['asset_root']==bank.relative_to(project).as_posix()
    assert definition['scenarios'][0]['resources']['database'][0]['asset_root']==bank.relative_to(project).as_posix()
    assert {p:file_hash(p) for p in original}==original
    assert len(list(project.joinpath('src/test/resources/shared-test-assets').rglob('manifest.json')))==2
    reused=generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=model)
    assert reused['origin']=='cached_generation' and len(calls)==1
    assert calls[0]['comparison_case_limit']==64


def test_bad_model_selections_do_not_reset_the_preparation_budget(tmp_path):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    proposal['scenarios'][0]['input_xml']['bank']='0'*64
    calls=[]
    model=lambda *args:calls.append(True) or json.dumps(proposal)
    assert generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=model)['status']=='unavailable'
    assert len(calls)==2
    assert generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=model)['status']=='unavailable'
    assert len(calls)==2 and not demo_artifact(project,'operation-demo-scenarios.json').exists()


def test_user_edited_definitions_and_overlays_are_preserved(tmp_path):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    assert generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=lambda *args:json.dumps(proposal))['status']=='prepared'
    path=demo_artifact(project,'operation-demo-scenarios.json');edited=json.loads(path.read_text())
    edited['scenarios'][0]['expected_resource_executions']=2;path.write_text(json.dumps(edited))
    original=path.read_bytes()
    assert generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=lambda *args:pytest.fail('User definition was overwritten'))['origin']=='retained_definition'
    assert path.read_bytes()==original
    overlay=project/'demo-values.yaml';overlay.write_text('# User-owned overlay\nimage: {repository: custom, digest: ""}\n')
    data=overlay.read_bytes()
    result=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port())
    assert result['status']=='prepared' and 'preserved' in result['overlay_notice']
    assert overlay.read_bytes()==data


def test_unavailable_generated_overlay_upgrades_automatically(tmp_path):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    assert prepare_operation_demo(project,root,'INTERNET/Example')['status']=='unavailable'
    assert generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=lambda *args:json.dumps(proposal))['status']=='prepared'
    result=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port())
    assert result['status']=='prepared',result
    from runtime.service_generation.deployment_configuration import read_deployment
    assert read_deployment(project/'values.yaml',overlays=[project/'demo-values.yaml']).demoInfrastructure.status=='prepared'
    assert (project/'standalone/demo-request.xml').read_text()=='<Request><Id>7</Id></Request>'


def test_assembly_prepares_scenarios_without_resuming_the_conversion(tmp_path):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    conn=sqlite3.connect(':memory:');conn.execute('CREATE TABLE untouched (value)');conn.execute('INSERT INTO untouched VALUES (7)')
    before=list(conn.iterdump());calls=[]
    from runtime.operation_assembly.values import prepare_operation_values
    cfg=SimpleNamespace(run_id='fixture',source_root=str(tmp_path),output_root=str(root))
    (project/'package-standalone-operation.bat').unlink()
    (project/'.gitignore').unlink()
    result=prepare_operation_values(conn,cfg,tmp_path,dict(project=str(project),channel='INTERNET',operation_id='Example'),
        profile=profile,model_call=lambda *args:calls.append(True) or json.dumps(proposal))
    assert result['scenario_generation']['status']=='prepared' and result['demo']['status']=='prepared',result
    assert len(calls)==1 and list(conn.iterdump())==before
    assert (project/'package-standalone-operation.bat').is_file() and (project/'.gitignore').is_file()


def test_exact_saved_query_reuse_preserves_link_values_and_case(tmp_path):
    root,project,bank,profile,raw=setup_operation(tmp_path)
    from models.operation_demo_proposal import OperationDemoProposal
    from runtime.fixture_demo.scenario_publication import validate_proposal
    from runtime.fixture_demo.scenario_reuse import reuse_saved_resources
    evidence,_=collect_scenario_evidence(project,'INTERNET/Example')
    old_bank=next(iter(evidence['saved_banks']))
    old_query=evidence['saved_banks'][old_bank]['fixtures']['fixtures']['database']['value']['queries'][0]
    first=dict(sql='{call VALUE(?)}',parameters=[],out_parameters={'1':dict(sql_type=4,value=7)})
    raw['new_fixtures']['db']=dict(kind='database',value=dict(queries=[first,old_query]))
    scenario=raw['scenarios'][0];scenario['resources']={'database':[dict(bank='generated',fixture_id='db',pointer='')]}
    scenario['links']=[dict(producer=dict(bank='generated',fixture_id='db',pointer='/queries/0/out_parameters/1/value'),
        consumer=dict(bank='generated',fixture_id='db',pointer='/queries/1/parameters/0'))]
    proposal=OperationDemoProposal.model_validate(raw)
    transformed,notes=reuse_saved_resources(proposal,evidence)
    assert notes[0]['reused_query_count']==1
    assert len(transformed.new_fixtures['db'].value['queries'])==1
    assert transformed.scenarios[0].links[0].consumer.bank==old_bank
    validate_proposal(transformed,evidence,2000000,64)
    # A case difference is not repaired or normalized to force reuse.
    raw['new_fixtures']['db']['value']['queries'][1]=dict(old_query,sql=old_query['sql'].lower())
    assert not reuse_saved_resources(OperationDemoProposal.model_validate(raw),evidence)[1]


def test_valid_saved_response_can_be_revalidated_without_a_new_model_call(tmp_path,monkeypatch):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    import runtime.fixture_demo.scenario_generation as generation
    original=generation.validate_proposal;calls=[]
    monkeypatch.setattr(generation,'validate_proposal',lambda *args:(_ for _ in ()).throw(ValueError('Old validator defect')))
    assert generation.generate_operation_scenarios(project,'INTERNET/Example',profile,
        model_call=lambda *args:calls.append(True) or json.dumps(proposal))['status']=='unavailable'
    assert len(calls)==2
    monkeypatch.setattr(generation,'validate_proposal',original)
    assert generation.generate_operation_scenarios(project,'INTERNET/Example',profile,
        model_call=lambda *args:pytest.fail('Saved candidate was regenerated'))['status']=='prepared'
    state=json.loads(next(demo_artifact(project,'.demo-scenario-generation').glob('*/state.json')).read_text())
    assert len(state['attempts'])==2 and any(a.get('revalidated') for a in state['attempts'])


def test_xml_fragment_expectations_follow_the_existing_comparator(tmp_path):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    proposal['new_fixtures']['expected']['value']='<First/><Second>text</Second>'
    result=generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=lambda *args:json.dumps(proposal))
    assert result['status']=='prepared',result
    assert prepare_operation_demo(project,root,'INTERNET/Example',port=free_port())['status']=='prepared'


def test_selected_composer_xml_is_available_as_literal_citation_evidence(tmp_path):
    import hashlib
    from runtime.fixture_demo.scenario_evidence import original_operation_evidence
    xml=tmp_path/'definitions.xml';xml.write_bytes(b'<XML><fmtDef id="Example"><CCString dataName="ExactCase"/></fmtDef></XML>')
    definition=dict(definition_id='fmt-id',kind='format',entity_id='Example',source_relative_path='definitions.xml',
        source_selector='/XML[1]/fmtDef[1]',source_hash=hashlib.sha256(xml.read_bytes()).hexdigest())
    conn=sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE scoped_source_definitions (run_id,definition_id,record_json)')
    conn.execute('INSERT INTO scoped_source_definitions VALUES (?,?,?)',('r','fmt-id',json.dumps(definition)))
    conn.execute('CREATE TABLE conversion_component_plans (run_id,plan_json)')
    conn.execute('INSERT INTO conversion_component_plans VALUES (?,?)',('r',json.dumps(dict(components={
        'component':dict(operations=['INTERNET/Example'],provenance=dict(source_definition_id='fmt-id'),configuration={})}))))
    result=original_operation_evidence(conn,SimpleNamespace(run_id='r',source_root=str(tmp_path)),'INTERNET/Example',{})
    assert result['sources'][0]['identity']=='fmt-id' and 'dataName="ExactCase"' in result['sources'][0]['content']


@pytest.mark.parametrize('actual,failed,queries,passed',[
    ('<Result>saved-value</Result>',False,1,True),
    ('<Result>wrong</Result>',False,1,False),
    ('<Result>saved-value</Result>',True,1,False),
    ('<Result>saved-value</Result>',False,0,False)])
def test_verification_checks_expected_xml_and_replay_not_just_exit_status(tmp_path,actual,failed,queries,passed):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    assert generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=lambda *args:json.dumps(proposal))['status']=='prepared'
    def run(project,request):
        assert request.read_text()=='<Request><Id>7</Id></Request>'
        report=project/'standalone/.demo-runtime/last-run.json';report.parent.mkdir(parents=True)
        report.write_text(json.dumps(dict(status='completed',execution='new-invocation',
            replay=dict(failed=failed,events=[dict(operation='execute') for _ in range(queries)]))))
        return subprocess.CompletedProcess([],0,actual,'')
    result=verify_operation_scenario(project,'INTERNET/Example',profile,run=run,validate_build=False)
    assert (result['status']=='verified_against_prepared_expectations')==passed,result
    assert result['java_and_pom_unchanged']
    assert demo_artifact(project,'.demo-scenario-verification').joinpath('result.json').is_file()
    assert not any((project/name).exists() for name in ARTIFACT_NAMES)


def test_legacy_migration_preserves_cached_ai_history_and_runtime_files(tmp_path):
    root,project,bank,profile,proposal=setup_operation(tmp_path)
    generated=generate_operation_scenarios(project,'INTERNET/Example',profile,model_call=lambda *args:json.dumps(proposal))
    assert generated['status']=='prepared',generated
    assert prepare_operation_demo(project,root,'INTERNET/Example',port=free_port())['status']=='prepared'
    verification=demo_artifact(project,'.demo-scenario-verification');verification.mkdir()
    (verification/'result.json').write_text('{"retained":"old verification"}')
    # Reproduce an old project, including the absolute proposal pointer it saved.
    for name in ARTIFACT_NAMES:
        demo_artifact(project,name).rename(project/name)
    head=project/'.demo-scenario-generation/current.json'
    previous=json.loads(head.read_text())
    previous['proposal']=str(project/'.demo-scenario-generation'/Path(previous['proposal']).relative_to(demo_artifact(project,'.demo-scenario-generation')))
    head.write_text(json.dumps(previous))
    legacy={str(path.relative_to(project)):path.read_bytes() for name in ARTIFACT_NAMES
        for path in ([project/name,*((project/name).rglob('*'))] if (project/name).is_dir() else [project/name]) if path.is_file()}
    runtime={path:file_hash(path) for path in [project/'standalone/operation.json',project/'standalone/demo-request.xml',
        project/'demo-values.yaml',*bank.iterdir()]}
    reused=generate_operation_scenarios(project,'INTERNET/Example',profile,
        model_call=lambda *args:pytest.fail('Migration regenerated the scenario'))
    assert reused['origin']=='cached_generation',reused
    assert not any((project/name).exists() for name in ARTIFACT_NAMES)
    assert all((demo_workspace(project)/name).read_bytes()==raw for name,raw in legacy.items())
    assert all(file_hash(path)==old for path,old in runtime.items())
    assert saved_generation_proposal(project,previous['proposal']).is_file()
    # Approval still hashes the external definition; fixture resolution stays project-relative.
    from runtime.service_generation.deployment_configuration import read_deployment
    from runtime.fixture_demo.approval import demo_evidence
    deployment=read_deployment(project/'values.yaml',overlays=[project/'demo-values.yaml'])
    evidence=demo_evidence(project,deployment.demoInfrastructure)
    assert evidence['definition_hash']==file_hash(demo_artifact(project,'operation-demo-scenarios.json'))


@pytest.mark.parametrize('conflict',['different_copy','active_lock'])
def test_migration_rejects_conflicts_before_moving_any_history(tmp_path,conflict):
    project=tmp_path/'generated/INTERNET/Example';project.mkdir(parents=True)
    owner=project/'.demo-owned-files.json';owner.write_text('{"binding":"retained"}')
    journal=project/'.demo-scenario-generation';journal.mkdir()
    state=journal/'state.json';state.write_text('{"attempts":[{"number":1}]}')
    if conflict=='different_copy':
        target=demo_artifact(project,'.demo-owned-files.json');target.parent.mkdir(parents=True)
        target.write_text('{"binding":"different"}')
    else:
        (journal/'state.json.lock').write_text('')
    before={path:path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    with pytest.raises(ValueError):migrate_demo_artifacts(project)
    assert prepare_operation_demo(project,project.parent.parent,'INTERNET/Example')['status']=='unavailable'
    assert {path:path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}==before


def test_migration_can_complete_identical_partial_copies_and_isolate_operations(tmp_path):
    project=tmp_path/'generated/INTERNET/Example';project.mkdir(parents=True)
    source=project/'demo-preparation.json';source.write_text('{"status":"prepared"}')
    target=demo_artifact(project,'demo-preparation.json');target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    migrate_demo_artifacts(project)
    assert not source.exists() and target.read_text()=='{"status":"prepared"}'
    assert demo_workspace(project)!=demo_workspace(tmp_path/'generated/SME/Example')
    with pytest.raises(ValueError):saved_generation_proposal(project,tmp_path/'outside.json')
