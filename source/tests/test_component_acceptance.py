"""CF7 acceptance uses actual whole-unit evidence, never component-validity flags alone."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from runtime.component_conversion.unit_artifacts import (load_unit_artifacts,save_unit_component_receipt,
    require_unit_components,require_partition_records)
from runtime.component_conversion.unit_binding import resolve_checklist,native_unit_binding
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tools.state_store_tools import component_records as records
from tools.state_store_tools.behavior_units import save
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from test_component_state import state,cache_all
from test_component_formats import format_case,boundary_tool,candidate
from test_scoped_vault_identity import scoped_mapper


def test_transitive_receipt_rejects_missing_results_mutated_artifacts_and_changed_heads(state):
    conn,plan,profile,output,source=state
    # Synthetic state fixtures exercise integrity only, not JVM/unit acceptance.
    _,_,saved=cache_all(conn,plan,profile,output/'components')
    config=SimpleNamespace(run_id='run',output_root=str(output))
    unit='step-1'
    artifacts=load_unit_artifacts(conn,config,profile,plan,unit)
    revision=save_unit_component_receipt(conn,config,artifacts,'candidate')
    assert require_unit_components(conn,config,unit,'candidate',revision=revision)
    root_group=next(group for group in plan.groups if plan.unit_roots[unit] in group.members)
    old=records.head(conn,'run',root_group.group_id)
    conn.execute("UPDATE conversion_component_heads SET result_revision='changed' WHERE run_id='run' AND group_id=?",(root_group.group_id,))
    with pytest.raises(ValueError,match='dependency revision changed'):
        require_unit_components(conn,config,unit,'candidate',revision=revision)
    conn.execute("UPDATE conversion_component_heads SET result_revision=? WHERE run_id='run' AND group_id=?",(old['result_revision'],root_group.group_id))
    dependency=next(key for key in artifacts['proof']['heads'] if key!=root_group.group_id)
    target=next(key for key,value in saved.items() if next(group.group_id for group in plan.groups if key in group.members)==dependency)
    path=Path(saved[target].artifact_root)/next(name for name in saved[target].files if name.startswith('src/main/java/'))
    path.write_text(path.read_text()+'// changed',encoding='utf-8')
    with pytest.raises(ValueError,match='bytes changed'):
        require_unit_components(conn,config,unit,'candidate',revision=revision)


def test_partial_root_cannot_be_promoted_and_sibling_state_is_preserved(state):
    conn,plan,profile,output,_=state
    cache_all(conn,plan,profile,output/'components')
    config=SimpleNamespace(run_id='run',output_root=str(output));unit=next(iter(plan.unit_roots))
    root=next(group.group_id for group in plan.groups if plan.unit_roots[unit] in group.members)
    before={group.group_id:records.head(conn,'run',group.group_id) for group in plan.groups if group.group_id!=root}
    records.invalidate(conn,'run',[root])
    with pytest.raises(ValueError,match='not component_validated'):
        load_unit_artifacts(conn,config,profile,plan,unit)
    assert all(records.head(conn,'run',key)==value for key,value in before.items())
    assert conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category='unit_verification' AND status='accepted'").fetchone()[0]==0


def test_component_invalidation_demotes_only_dependent_unit_acceptance(state):
    conn,plan,profile,output,_=state
    cache_all(conn,plan,profile,output/'components')
    config=SimpleNamespace(run_id='run',output_root=str(output))
    for identity in plan.unit_roots:
        save_unit_component_receipt(conn,config,load_unit_artifacts(conn,config,profile,plan,identity),'candidate')
        # Explicit state-only fixture; real evidence acceptance is covered by the JVM test.
        save(conn,'run','unit_verification',identity,'synthetic',dict(unit_id=identity,status='accepted'))
    root=next(group.group_id for group in plan.groups if plan.unit_roots['step-1'] in group.members)
    records.invalidate(conn,'run',[root])
    statuses={row['identity']:row['status'] for row in conn.execute("SELECT identity,status FROM behavior_snapshots WHERE category='unit_verification'")}
    assert statuses=={'step-1':'verification_incomplete','other-step':'accepted'}


def test_whole_unit_repair_targets_only_its_configured_root(state,monkeypatch):
    from contextlib import nullcontext
    from runtime.component_conversion.unit_provider import ComponentUnitProvider
    from runtime.behavior_conversion.verification_feedback import VerificationFailure
    from tools.state_store_tools.behavior_units import snapshot
    conn,plan,profile,output,_=state
    cache_all(conn,plan,profile,output/'components')
    root=next(group.group_id for group in plan.groups if plan.unit_roots['step-1'] in group.members)
    unchanged={group.group_id:records.head(conn,'run',group.group_id) for group in plan.groups if group.group_id!=root}
    provider=ComponentUnitProvider.__new__(ComponentUnitProvider)
    provider.conn,provider.plan,provider.profile=conn,plan,profile
    provider.config=SimpleNamespace(run_id='run',output_root=str(output))
    provider.preparation,provider.classpath,provider.boundaries,provider.units={},None,{},{}
    provider.factory,provider.model_call=None,None
    calls=[]
    monkeypatch.setattr('runtime.component_conversion.scope.component_execution',lambda *a,**k:nullcontext())
    monkeypatch.setattr('runtime.component_conversion.runner._convert_group',lambda *args,**kw:calls.append(args[4].group_id))
    feedback=dict(stage='boundary',failing_cases=[dict(input='same',difference='literal prefix')])
    provider._repair(SimpleNamespace(unit_id='step-1'),VerificationFailure(feedback))
    assert calls==[root] and records.head(conn,'run',root)['status']=='stale'
    assert all(records.head(conn,'run',key)==value for key,value in unchanged.items())
    assert json.loads(snapshot(conn,'run','component_unit_feedback',root)['data_json'])==feedback


@pytest.mark.parametrize('incomplete',[False,True])
def test_unit_correction_limits_do_not_retry_capability_gaps(monkeypatch,incomplete):
    from runtime.component_conversion.unit_provider import ComponentUnitProvider
    from runtime.behavior_conversion.verification_feedback import VerificationFailure
    from models.scoped_configured_unit import ScopedConfiguredUnit
    from tools.behavior_verification.boundary_contracts import boundary_contract
    from test_component_graph import step
    unit=ScopedConfiguredUnit.model_validate(step('unit'))
    provider=ComponentUnitProvider.__new__(ComponentUnitProvider)
    provider.conn,provider.config,provider.profile=None,None,PipelineConfiguration(max_agent_task_retries=2)
    provider.plan,provider.model_call=None,None
    provider.boundaries={'boundaries':{'unit':boundary_contract(unit.model_dump(mode='json')).model_dump(mode='json')}}
    monkeypatch.setattr('runtime.scoped_native.scope.require_task',lambda *a:None)
    monkeypatch.setattr('runtime.component_conversion.unit_provider.load_unit_artifacts',lambda *a:{})
    monkeypatch.setattr('runtime.component_conversion.unit_provider.resolve_checklist',lambda *a:None)
    calls=[];repairs=[]
    def fail(*args):
        calls.append('attempt')
        raise (VerificationIncomplete if incomplete else VerificationFailure)(dict(stage='test_control_flow'))
    monkeypatch.setattr('runtime.component_conversion.unit_provider.native_unit_binding',fail)
    provider._repair=lambda *args:repairs.append('root')
    with pytest.raises(VerificationFailure):
        provider(unit,{},lambda *args:None)
    assert len(calls)==(1 if incomplete else 2) and len(repairs)==(0 if incomplete else 1)


def checklist_fixture():
    item=dict(id='literal',source_identity='java:Source',source_hash='hash')
    location=dict(path='src/main/java/Native.java',excerpt='return 1;')
    artifacts=dict(root_report={},files={location['path']:'class Native { int run(){return 1;} }'},reports={
        'helper':dict(parser_checklist=[item],checklist_implementations={'literal':[location]})})
    boundary=dict(unit_id='unit',source_manifest_hash='manifest',configuration_hash='config',parser_checklist=dict(items=[deepcopy(item)]))
    return artifacts,boundary


def test_master_checklist_resolves_real_dependency_locations_and_rejects_missing_items():
    artifacts,boundary=checklist_fixture()
    answers=resolve_checklist(artifacts,boundary)
    assert answers.responses[0].locations[0].excerpt=='return 1;'
    boundary['parser_checklist']['items'].append(dict(id='missing',source_identity='java:Other',source_hash='other'))
    with pytest.raises(VerificationIncomplete,match='missing'):
        resolve_checklist(artifacts,boundary)
    boundary['parser_checklist']['items'].pop()
    artifacts['files'].clear()
    with pytest.raises(VerificationIncomplete,match='missing_item_ids'):
        resolve_checklist(artifacts,boundary)


def test_checklist_identity_cannot_cross_original_source_revisions():
    artifacts,boundary=checklist_fixture()
    boundary['parser_checklist']['items'][0]['source_hash']='new-source'
    with pytest.raises(ValueError,match='provenance'):
        resolve_checklist(artifacts,boundary)


def test_subtree_receipts_participate_in_transitive_packaging_checks(state):
    conn,_,_,output,_=state;config=SimpleNamespace(run_id='run',output_root=str(output))
    identity='a'*64;folder=output/'components/format-parts/group';folder.mkdir(parents=True)
    artifact=folder/'part';artifact.mkdir();(artifact/'Native.java').write_text('part')
    from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
    record=dict(artifact='part',manifest={'Native.java':file_digest(artifact/'Native.java')})
    save(conn,'run','format_subtree_artifact',identity,digest(record),record,status='component_validated')
    receipt=folder/(identity+'.json');receipt.write_text(json.dumps(record))
    require_partition_records(conn,config,'group',[identity])
    (artifact/'Native.java').write_text('tampered')
    with pytest.raises(ValueError,match='changed or disappeared'):
        require_partition_records(conn,config,'group',[identity])
    with pytest.raises(ValueError,match='Invalid subtree'):
        require_partition_records(conn,config,'group',['../escape'])


def test_step_binding_request_is_metadata_only_and_runs_whole_unit_validator(monkeypatch):
    captured=[]
    def generate(*args,**kwargs):
        captured.append(args)
        from models.component_unit_binding import ComponentUnitBinding
        binding=ComponentUnitBinding(verification_binding=dict(owner_type='com.company.generated.Step',method_name='execute'))
        kwargs['validator'](binding)
        return binding,'fingerprint'
    monkeypatch.setattr('runtime.component_conversion.unit_binding.generate',generate)
    unit=SimpleNamespace(unit_id='step',kind='configured_step',logical_id='Step',effective_configuration={},configuration_xml='<opStep/>')
    artifacts=dict(root_report=dict(owned_sources=['src/main/java/Step.java']),proof={},contract=dict(apis=[]),files={'src/main/java/Step.java':'source'})
    checked=[]
    bundle=native_unit_binding(None,None,PipelineConfiguration(),unit,artifacts,lambda metadata:metadata,lambda bundle,**kw:checked.append(bundle),None)
    assert bundle.verification_binding.method_name=='execute' and len(checked)==1
    assert captured[0][3]=='unit_binding' and captured[0][7].__name__=='ComponentUnitBinding'
    assert 'files' not in captured[0][6]


def test_component_packaging_requires_component_receipt_even_with_an_accepted_status(state):
    from runtime.behavior_conversion.verification_state import require_unit_receipts
    conn,_,_,output,_=state
    save(conn,'run','unit_verification','step-1','synthetic',dict(verification_version='parser-boundary-v1'))
    with pytest.raises(ValueError,match='transitive component acceptance'):
        require_unit_receipts(conn,SimpleNamespace(run_id='run',output_root=str(output)),
            dict(component_first=True,bindings={'step':dict(unit_id='step-1',files={})}))


def test_binding_task_is_available_only_in_explicit_component_mode(monkeypatch):
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.scoped_native.scope import native_execution,require_task
    monkeypatch.setattr('runtime.scoped_native.scope.validate_checkpoints',lambda *a:None)
    config=SimpleNamespace(run_id='scope');unit=SimpleNamespace(unit_id='unit')
    profile=PipelineConfiguration(conversion_strategy='behavior_units',scoped_native_mode='behavior_units_v1')
    with native_execution(None,config,profile,None,{'SME/Op':[unit]}),pytest.raises(ValueError,match='Unsupported scoped generation'):
        require_task(None,config,profile,'unit_binding','unit',{})
    profile=profile.model_copy(update={'scoped_native_mode':'component_first_v1'})
    with native_execution(None,config,profile,None,{'SME/Op':[unit]}):
        assert require_task(None,config,profile,'unit_binding','unit',{})[1:] == ('SME/Op','unit')


def test_unit_specific_requirements_reach_configured_component_generation(format_case):
    from models.conversion_requirement import ConversionRequirement
    from runtime.component_conversion.requests import build_component_request
    from tools.conversion_tools.component_identity import component_group
    _,_,profile,_,plan,boundaries,units=format_case
    profile.conversion_requirements=[ConversionRequirement(requirement_id='unit-only',version=2,
        description='Preserve the configured source exception contract',applies_to=['unit'])]
    group=component_group(plan,plan.unit_roots['response'])
    request,_=build_component_request(plan,group,boundaries,[],profile,units=units)
    assert request['requirements']['unit-only']=='Preserve the configured source exception contract'


def test_component_mode_handoff_preserves_scoped_gates_and_reports_pending_units(tmp_path,scoped_mapper,monkeypatch):
    from tests.runtime.test_scoped_native import scoped_state
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.scoped_native.runner import resume_scoped_pipeline
    from runtime.workspace_paths import write_run_report,run_report_path
    from runtime.java_toolchain import java_scope,resolve_java_home
    from tools.state_store_tools.runs import update_run_status
    conn,config=scoped_state(tmp_path,scoped_mapper)
    profile=PipelineConfiguration(source_root=config.source_root,mapper_vault_layout='scoped',source_workspace_id='native',
        scoped_native_mode='component_first_v1',scoped_java_project='.',conversion_strategy='behavior_units',
        plan_approval_policy='automatic',java_version=25,java_home=resolve_java_home(25),model_provider='mock',
        gate_policies={str(number):'automatic' for number in range(1,5)},classpath_jars=[],eclipse_classpath_variables={})
    calls=[];provider=object()
    def components(conn,config,profile,directory,*args,**kwargs):
        calls.append('components')
        write_run_report(directory,'component-generation.json',json.dumps(dict(groups={'fixture':dict(status='component_validated')})))
    monkeypatch.setattr('runtime.component_conversion.runner.convert_basic_components',components)
    monkeypatch.setattr('runtime.component_conversion.unit_provider.ComponentUnitProvider',lambda *args:provider)
    def unit_flow(*args,**kwargs):
        calls.append('units')
        assert kwargs['component_provider'] is provider
        from tools.state_store_tools.runs import get_run
        assert get_run(conn,config.run_id)['status']=='in_progress'
        assert get_run(conn,config.run_id)['current_phase']=='conversion_units_verifying'
        update_run_status(conn,config.run_id,'blocked','fixture_no_unit_acceptance')
    monkeypatch.setattr('runtime.behavior_conversion.runner._convert_and_review',unit_flow)
    try:
        with java_scope(profile):
            resume_scoped_pipeline(conn,config,profile,tmp_path/'reports',model_call=lambda *args:pytest.fail('No model requested by this handoff fixture'))
        report=json.loads(run_report_path(tmp_path/'reports','scoped_native_execution.json').read_text())
        assert calls==['components','units'] and report['capability']=='component-first-cf7'
        assert report['unit_verification']['accepted']==report['accepted_operations']==0 and report['pending_units']==2
    finally:
        conn.close()


def test_real_maven_component_format_is_promoted_only_after_whole_unit_checks_and_reuses(format_case,tmp_path,monkeypatch):
    from tests.runtime.test_scoped_native import actual_build
    from runtime.component_conversion.runner import convert_basic_components
    from runtime.component_conversion.unit_provider import ComponentUnitProvider
    from runtime.behavior_conversion.verification_units import generate_verified_unit
    from runtime.behavior_conversion.runner import _bundle_validator
    from runtime.behavior_conversion.testing_contract import attach_testing_contract
    from runtime.scoped_native.scope import native_execution
    from models.scoped_configured_unit import ScopedConfiguredUnit
    from tools.state_store_tools.behavior_units import snapshot
    from runtime.behavior_conversion.verification_state import require_unit_receipts
    conn,config,profile,preparation,plan,_,units=format_case
    # Reduce the fixture to one selected direction; original source/harness remain real.
    preparation=deepcopy(preparation);preparation['operations']['XML/Flow']['units']=[units['response']]
    from tools.conversion_tools.component_graph import build_component_plan
    plan=build_component_plan(preparation['operations']);preparation['component_plan']=plan.model_dump(mode='json')
    calls=[]
    def model(instruction,encoded):
        request=json.loads(encoded);calls.append(request)
        return json.dumps(candidate(request))
    convert_basic_components(conn,config,profile,tmp_path/'component-run',preparation,None,model_call=model,context_factory=actual_build,include_formats=True)
    assert len(calls)==2
    assert {node['label'] for request in calls for node in request['components'].values()}=={'example.SimpleFormat','response'}
    unit=ScopedConfiguredUnit.model_validate(dict(units['response'],schema_version='scoped-component-unit-v1'))
    monkeypatch.setattr('runtime.scoped_native.scope.validate_checkpoints',lambda *args:None)
    # Fixture has no imported-vault checkpoint ledger; the real scoped ledger is covered by regression tests.
    ledger=[];monkeypatch.setattr('runtime.scoped_native.results.record_result',lambda *args:ledger.append(args))
    provider=ComponentUnitProvider(conn,config,profile,preparation,None,actual_build,lambda *args:pytest.fail('Format promotion must reuse built code'))
    project=Path(config.output_root)/'XML/Flow'
    payload=unit.model_dump(mode='json');evidence=[unit.unit_id,*[source.identity for source in unit.sources]]
    payload.update(requirements={'business':'Preserve configured behavior'},evidence_ids=evidence)
    attach_testing_contract(payload,profile)
    validator=_bundle_validator(conn,config,profile,project,unit.unit_id,(),payload['requirements'],evidence,actual_build)
    with native_execution(conn,config,profile,None,{'XML/Flow':[unit]}):
        bundle,_,review,_=generate_verified_unit(conn,config,profile,unit.unit_id,'',payload,validator,
            bundle_generator=lambda request:provider(unit,request,validator))
        assert review.approved
        # Warm acceptance rechecks the full ladder without generating new Java or metadata.
        generate_verified_unit(conn,config,profile,unit.unit_id,'',payload,validator,
            bundle_generator=lambda request:provider(unit,request,validator))
    receipt=snapshot(conn,config.run_id,'unit_verification',unit.unit_id)
    assert receipt['status']=='accepted' and json.loads(receipt['data_json'])['component_receipt']
    manifest=json.loads(snapshot(conn,config.run_id,'manifest',unit.unit_id)['data_json'])
    record=dict(component_first=True,bindings={'response':dict(unit_id=unit.unit_id,files=manifest['files'])})
    require_unit_receipts(conn,config,record)
    assert len(ledger)==2 and conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category='operation'").fetchone()[0]==0
    root=next(group.group_id for group in plan.groups if plan.unit_roots[unit.unit_id] in group.members)
    records.invalidate(conn,config.run_id,[root])
    with pytest.raises(ValueError,match='dependency revision changed|technical boundary acceptance'):
        require_unit_receipts(conn,config,record)
