"""Opt-in citation-free verification preserves real build and isolated comparison gates."""
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.executable_verification_settings import ExecutableVerificationSettings
from models.native_unit_bundle import NativeUnitBundle
from models.unit_verification_boundary import UnitVerificationBoundary
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete
from runtime.behavior_conversion.bundle_output import accept_bundle,validate_bundle
from runtime.behavior_conversion.verification_state import record_verification,require_unit_receipts
from tools.behavior_verification.boundaries import build_boundary_report
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.runs import upsert_run
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first
from test_typed_boundary_adapter import ROOT


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


def fixture(tool,tmp_path,value=7):
    original=unit(sources=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),
        source('work','package example; public class Work { public void setContext(com.ibm.dse.base.Context c){} public int execute(){return 7;} }')])
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=tool)))
    package='com.company.generated.executable'
    main='src/main/java/'+package.replace('.','/')+'/Work.java'
    test=main.replace('src/main/','src/test/').replace('Work.java','WorkTest.java')
    bundle=NativeUnitBundle(files=[dict(path=main,content='package '+package+'; public class Work { public int execute(){return '+str(value)+';} public int unusedHelper(){return 99;} }'),
        dict(path=test,content='package '+package+'; public class WorkTest { @org.junit.jupiter.api.Test public void runs(){org.junit.jupiter.api.Assertions.assertEquals('+str(value)+',new Work().execute());}}')],
        unit_contract=dict(unit_id=original['unit_id'],apis=[dict(type_name=package+'.Work',method_signatures=['public int execute()'])],requirements={'result':'Preserve original result'},evidence_ids=['work']),
        verification_binding=dict(owner_type=package+'.Work',method_name='execute'))
    config=SimpleNamespace(output_root=str(tmp_path),run_id='executable')
    settings=ExecutableVerificationSettings(mode='executable_boundary_v1')
    return original,bundle,config,UnitVerificationSession(config,original,boundary,tool=tool,executable_settings=settings)


def test_rollout_is_explicit_and_policy_is_fingerprinted():
    from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy
    old=PipelineConfiguration();new=old.model_copy(deep=True)
    new.executable_verification.mode='executable_boundary_v1'
    assert old.executable_verification.mode=='checklist_v1'
    assert conversion_policy(old)!=conversion_policy(new)
    with pytest.raises(ValueError):ExecutableVerificationSettings(mode='silently_skip_checks')
    with pytest.raises(ValueError,match='requires staged_unit_conversion'):
        PipelineConfiguration(staged_unit_conversion=False,executable_verification={'mode':'executable_boundary_v1'})


@pytest.mark.parametrize('value',[7,8])
def test_real_maven_and_jvm_comparison_without_citations(boundary_tool,tmp_path,value):
    from tests.runtime.test_scoped_native import actual_build
    from runtime.behavior_conversion.testing_contract import testing_contract
    original,bundle,config,session=fixture(boundary_tool,tmp_path,value)
    assert bundle.checklist_answers is None and not bundle.behavior_implementations
    session.static(bundle)
    profile=PipelineConfiguration(java_version=25)
    def compare(project,context,validation):session.compare(project,context,bundle,build_validation=validation.model_dump(mode='json'))
    def build():return accept_bundle(tmp_path/'project',validate_bundle(bundle),actual_build,profile,[],
        testing_contract=testing_contract(profile),required_tests=[bundle.files[1].path],pre_publish=compare)
    if value==8:
        with pytest.raises(VerificationFailure) as error:build()
        assert error.value.verification_feedback['stage']=='boundary'
        assert not (tmp_path/'project'/bundle.files[0].path).exists()
        return
    validation,_=build()
    assert validation['tests_passed'] and validation['test_count']==1
    assert session.last_report['verification_version']=='executable-boundary-v1'
    assert session.last_report['observed_cases']>0 and not session.last_report['exhaustive_equivalence']
    conn=get_connection(':memory:');create_all_tables(conn);upsert_run(conn,run_id=config.run_id,run_mode='full_inventory')
    receipt=record_verification(conn,config,original['unit_id'],'accepted',session.last_report)
    import hashlib
    files={f.path:hashlib.sha256(f.content.encode()).hexdigest() for f in bundle.files}
    require_unit_receipts(conn,config,{'bindings':{'step':{'unit_id':original['unit_id'],'files':files}}})
    inputs=session.attempt/'input-cases.json';retained=inputs.read_text()
    inputs.write_text('{}')
    with pytest.raises(ValueError,match='Controlled input evidence changed'):
        require_unit_receipts(conn,config,{'bindings':{'step':{'unit_id':original['unit_id'],'files':files}}})
    inputs.write_text(retained)
    evidence=session.attempt/'boundary-structure.json';evidence.write_text('{}')
    with pytest.raises(ValueError,match='structural evidence changed'):require_unit_receipts(conn,config,{'bindings':{'step':{'unit_id':original['unit_id'],'files':files}}})
    conn.close()


def test_missing_adapter_and_missing_build_are_not_matches(boundary_tool,tmp_path):
    _,bundle,_,session=fixture(boundary_tool,tmp_path)
    bundle.verification_binding=None
    with pytest.raises(VerificationIncomplete,match='adapter'):session.static(bundle)
    _,bundle,_,session=fixture(boundary_tool,tmp_path)
    session.static(bundle)
    with pytest.raises(VerificationIncomplete,match='compilation'):session.compare(tmp_path,SimpleNamespace(),bundle)
    session.unit['configuration_xml']='<changed/>'
    with pytest.raises(VerificationIncomplete) as error:session.static(bundle)
    assert error.value.verification_feedback['stage']=='source_analysis'
    _,bundle,_,session=fixture(boundary_tool,tmp_path)
    session.static(bundle);session.executable_settings.seed+=1
    with pytest.raises(VerificationIncomplete,match='policy changed'):
        session.compare(tmp_path,SimpleNamespace(),bundle)
