"""Conversion readiness requires real mappings and JUnit, without a legacy execution harness."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import pytest
from models.native_unit_bundle import NativeUnitBundle
from models.maven_dependency import MavenDependency
from models.pipeline_configuration import PipelineConfiguration
from models.unit_verification_boundary import UnitVerificationBoundary
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession
from runtime.behavior_conversion.verification_state import _require_evidence,record_verification,require_unit_receipts
from runtime.behavior_conversion.verification_mode import conversion_mode,policy_payload
from runtime.java_toolchain import java_scope
from tools.behavior_verification.boundaries import build_boundary_report
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first

PATH='src/main/java/com/company/generated/Work.java'
CODE='package com.company.generated; public class Work { public int execute(){return 7;} }'


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


def profile():
    return PipelineConfiguration(java_version=25,model_provider='mock',staged_unit_conversion=True,
        executable_verification={'mode':'conversion_checklist_v1'})


def fixture(boundary_tool,tmp_path):
    original=unit(sources=[source('work','package example; public class Work { public int execute(){int value=7; return value;} }')])
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    assert boundary.parser_checklist and boundary.parser_checklist.status=='extracted'
    bundle=NativeUnitBundle(files=[dict(path=PATH,content=CODE)],unit_contract=dict(unit_id=original['unit_id'],
        apis=[dict(type_name='com.company.generated.Work',method_signatures=['public int execute()'])],
        requirements={'business':'Return original result'},evidence_ids=['work']),
        checklist_answers=dict(unit_id=original['unit_id'],source_manifest_hash=boundary.source_manifest_hash,
            configuration_hash=boundary.configuration_hash,responses=[dict(checklist_id=item.id,status='implemented',
                locations=[dict(path=PATH,excerpt='return 7;')]) for item in boundary.parser_checklist.items]))
    config=SimpleNamespace(output_root=str(tmp_path),run_id='conversion')
    session=UnitVerificationSession(config,original,boundary,tool=boundary_tool,executable_settings=profile().executable_verification)
    return config,session,bundle


def forbidden(*args,**kwargs):
    raise AssertionError('Legacy execution/comparison preparation must not run in conversion mode')


def forbid_comparison(monkeypatch):
    for module,name in [('runtime.behavior_conversion.verification_ladder','controlled_cases'),
        ('runtime.behavior_conversion.verification_ladder','verify_boundary'),
        ('runtime.behavior_conversion.verification_ladder','native_runtime_classpath'),
        ('tools.behavior_verification.supporting_static_checks','generate_boundary_cases'),
        ('tools.behavior_verification.static_checks','supporting_checks')]:
        monkeypatch.setattr(module+'.'+name,forbidden)
    monkeypatch.setattr(UnitVerificationSession,'compare',forbidden)


def test_policy_is_explicit_and_does_not_hash_unused_comparison_settings():
    value=profile();assert conversion_mode(value)
    before=policy_payload(value)
    value.executable_verification.clock_millis+=1
    value.executable_verification.comparison_mutations.enabled=False
    assert policy_payload(value)==before and before['equivalence']=='not_assessed'
    with pytest.raises(ValueError,match='bounded checklist batching'):
        PipelineConfiguration(staged_unit_conversion=True,metadata_checklist_batching=False,
            executable_verification={'mode':'conversion_checklist_v1'})


def test_mapping_preparation_needs_no_binding_or_known_call_whitelist(boundary_tool,tmp_path,monkeypatch):
    _,session,bundle=fixture(boundary_tool,tmp_path);forbid_comparison(monkeypatch)
    # Unfamiliar external call is source text here. Actual library availability remains a compiler check.
    bundle.files[0].content=CODE.replace('return 7;','new com.fasterxml.jackson.dataformat.xml.XmlMapper(); return 7;')
    assert bundle.verification_binding is None
    assert session.prepare_tests(bundle)['mapping_status']=='mapping_valid'
    assert session.static_report.comparison_requests==[] and session.static_report.comparison_cases=={}
    assert not (session.attempt/'comparison').exists()


def test_all_missing_items_are_reported_and_comment_only_evidence_fails(boundary_tool,tmp_path):
    _,session,bundle=fixture(boundary_tool,tmp_path)
    missing=len(bundle.checklist_answers.responses);assert missing>1
    bundle.checklist_answers.responses=[]
    with pytest.raises(ValueError,match='Missing checklist answer'):session.prepare_tests(bundle)
    assert len([e for e in session.static_report.errors if e.get('message')=='Missing checklist answer'])==missing
    _,session,bundle=fixture(boundary_tool,tmp_path)
    bundle.files[0].content=CODE.replace('return 7;','/* return 7; */ return 8;')
    with pytest.raises(ValueError,match='outside comments'):session.prepare_tests(bundle)


def test_readiness_rejects_unexecuted_tests_and_changed_candidate(boundary_tool,tmp_path,monkeypatch):
    _,session,bundle=fixture(boundary_tool,tmp_path);forbid_comparison(monkeypatch)
    session.prepare_tests(bundle)
    with pytest.raises(ValueError,match='executed JUnit'):
        session.complete(tmp_path,None,bundle,build_validation=dict(build_passed=True,tests_passed=True,test_count=0))
    bundle.files[0].content+='\n'
    with pytest.raises(ValueError,match='Candidate changed'):
        session.complete(tmp_path,None,bundle,build_validation=dict(build_passed=True,tests_passed=True,test_count=1))
    assert session.last_report is None


def test_real_maven_junit_then_readiness_receipt_and_tamper_detection(boundary_tool,tmp_path,monkeypatch):
    from tests.runtime.test_scoped_native import actual_build
    from runtime.behavior_conversion.bundle_output import accept_bundle
    from tools.state_store_tools.db import get_connection,create_all_tables
    from tools.state_store_tools.runs import upsert_run
    config,session,bundle=fixture(boundary_tool,tmp_path);forbid_comparison(monkeypatch)
    test_path='src/test/java/com/company/generated/WorkTest.java'
    from models.native_unit_bundle import NativeSourceFile
    bundle.files.append(NativeSourceFile(path=test_path,content='package com.company.generated; import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; public class WorkTest { @Test public void originalResult(){assertEquals(7,new Work().execute());} }'))
    bundle.dependencies=[MavenDependency(
        group_id='org.junit.jupiter',artifact_id='junit-jupiter',version='5.10.2',scope='test',reason='JUnit')]
    bundle.coverage={'business':[test_path]}
    session.prepare_tests(bundle)
    def finish(staged,context,result):
        session.complete(staged,context,bundle,build_validation=result.model_dump(mode='json'))
    validation,_=accept_bundle(tmp_path/'project',{f.path:f.content for f in bundle.files},actual_build,profile(),
        bundle.dependencies,required_tests=[test_path],pre_publish=finish)
    assert validation['tests_passed'] and validation['test_count']==1
    receipt=session.last_report
    assert receipt['readiness_status']=='conversion_ready' and receipt['behavioral_equivalence']=='not_assessed'
    assert not (session.attempt/'harness-tool.jar').exists()
    conn=get_connection(':memory:');create_all_tables(conn);upsert_run(conn,run_id=config.run_id,run_mode='single_channel')
    try:
        record_verification(conn,config,session.unit['unit_id'],'accepted',receipt)
        record=dict(bindings={'step':dict(unit_id=session.unit['unit_id'],files={f.path:hashlib.sha256(f.content.encode()).hexdigest() for f in bundle.files})})
        require_unit_receipts(conn,config,record,expected_version='conversion-checklist-v1')
        changed=deepcopy(receipt);changed['behavioral_equivalence']='passed'
        with pytest.raises(ValueError,match='does not match'):_require_evidence(config,session.unit['unit_id'],changed)
        (session.attempt/'static/unit-static-checks.json').write_text('{}',encoding='utf-8')
        with pytest.raises(ValueError,match='checklist evidence changed'):_require_evidence(config,session.unit['unit_id'],receipt)
    finally:conn.close()


def test_comparison_receipts_cannot_satisfy_new_policy():
    from tests.runtime.test_behavior_conversion import state
    from tools.state_store_tools.behavior_units import save
    conn,config=state()
    try:
        save(conn,config.run_id,'unit_verification','old','old',dict(verification_version='executable-boundary-v1'))
        with pytest.raises(ValueError,match='policy changed'):
            require_unit_receipts(conn,config,dict(bindings={'step':{'unit_id':'old'}}),expected_version='conversion-checklist-v1')
    finally:conn.close()


def test_service_finalization_does_not_request_or_claim_runtime_equivalence(tmp_path,monkeypatch):
    from tests.runtime.test_service_generation import ready,run
    from runtime.finalization import run_finalization
    from runtime.workspace_paths import run_report_path
    from pathlib import Path
    setup=ready(tmp_path);conn,config,settings,plan,_=setup
    settings.executable_verification.mode='conversion_checklist_v1'
    monkeypatch.setattr('runtime.runtime_validation.executor.RuntimeTestExecutor.execute',forbidden)
    assert run(tmp_path,setup)=='validation_evidence_pending'
    validation=json.loads(conn.execute('SELECT validation_json FROM service_generation_checkpoints').fetchone()[0])
    assert validation['behavioral_equivalence']=='not_assessed' and 'runtime_tests_simulated' not in validation
    settings.deployment_template_dir=str(Path(__file__).resolve().parents[1]/'templates/deployment')
    settings.deployment_values={'INTERNET/Op':dict(image_name='registry.example/service:1.0.0')}
    assert run_finalization(conn,config,settings,plan,tmp_path)=='gate_5_pending'
    delivery=json.loads(run_report_path(tmp_path,'delivery_manifest.json').read_text(encoding='utf-8'))
    assert delivery['conversion_ready'] and not delivery['production_ready']
    assert delivery['behavioral_equivalence']=='not_assessed' and not delivery['blockers']
    conn.close()


def test_mapping_batches_repair_only_bad_items_without_resetting_history():
    from test_metadata_checklist_integration import setup,reply
    from test_metadata_checklist import answer
    from runtime.behavior_conversion.metadata_checklist import map_checklist
    seen=[]
    def model(prompt,text):
        request=json.loads(text);seen.append(request)
        assert len(request['assigned_items'])<=2
        if len(seen)==1:
            return reply(request,[answer(request['assigned_items'][0]['id']),answer(request['assigned_items'][1]['id'],'missing')])
        if request['errors']:
            assert len(request['assigned_items'])==1
            assert request['errors'][0]['code']=='excerpt_not_found'
        return reply(request)
    tasks,payload,production=setup(model)
    tasks.profile.executable_verification.mode='conversion_checklist_v1'
    try:
        mapped=map_checklist(tasks,payload,production,{})
        assert len(mapped['checklist_implementations'])==6 and len(seen)==4
        tasks.model_call=forbidden
        assert map_checklist(tasks,payload,production,{})==mapped
        assert tasks.conn.execute('SELECT count(*) FROM metadata_checklist_attempts').fetchone()[0]==4
    finally:tasks.conn.close()
