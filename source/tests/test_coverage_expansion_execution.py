"""Real JVM probes, rather than proposed values, establish coverage gains."""
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.executable_verification_settings import ExecutableVerificationSettings
from models.unit_verification_boundary import UnitVerificationBoundary
from models.boundary_case import BoundaryCase
from models.boundary_harness_binding import BoundaryHarnessBinding
from runtime.java_toolchain import java_scope
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_verification import verify_boundary
from tools.behavior_verification.coverage_expansion import CoverageExpansion
from tools.behavior_verification.independent_comparison import VERSION
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first
from test_typed_boundary_adapter import ROOT


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


@pytest.mark.parametrize('broken',[False,True])
def test_clock_threshold_expansion_measures_real_probes(boundary_tool,tmp_path,broken):
    original=unit(sources=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),
        source('work','package example; public class Work { public void setContext(com.ibm.dse.base.Context c){} public int execute(){return System.currentTimeMillis()>1000?1:0;} }')])
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    left=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
    expression='1' if broken else 'System.currentTimeMillis()>1000?1:0'
    right=BoundaryHarnessBinding(adapter_class='fixture.Adapter',sources=[dict(path='fixture/Adapter.java',content=
        'package fixture; public class Adapter implements il.co.dcd.verification.harness.BoundaryAdapter { public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element configuration){return '+expression+';} }')])
    expansion=CoverageExpansion(original,boundary,ExecutableVerificationSettings(mode='executable_boundary_v1'),left)
    report=verify_boundary(original,boundary,left,right,[BoundaryCase(case_id='baseline',clock_millis=2000)],tmp_path/'comparison',
        tool=boundary_tool,candidate_label='coverage_fixture',comparison_policy=VERSION,coverage_expansion=expansion)
    assert not report.issues,report.issues
    assert len(report.cases)>1 and expansion.rounds,[(case['legacy']['exception'],case['native']['exception'],case['limitations']) for case in report.cases]
    assert not [branch for branch in report.coverage['branches'] if branch['unexercised_outcomes']],report.coverage
    assert report.status==('differences_found' if broken else 'matched_observed_cases')
    assert report.execution_environment['coverage_expansion']['executed_additional_cases']==len(report.cases)-1
    if broken:
        assert report.cases[0]['comparison_status']=='matched'
        assert any(case['comparison_status']=='different' for case in report.cases[1:])


@pytest.mark.parametrize('rounds,required',[(2,True),(0,True),(0,False)])
def test_real_build_coverage_gate_and_receipt(boundary_tool,tmp_path,rounds,required):
    from test_executable_verification import fixture
    from tests.runtime.test_scoped_native import actual_build
    from runtime.behavior_conversion.bundle_output import accept_bundle,validate_bundle
    from runtime.behavior_conversion.testing_contract import testing_contract
    from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
    from runtime.behavior_conversion.verification_state import record_verification,require_unit_receipts
    from tools.state_store_tools.db import get_connection,create_all_tables
    from tools.state_store_tools.runs import upsert_run
    import hashlib
    original,bundle,config,session=fixture(boundary_tool,tmp_path)
    original['sources'][-1]=source('work','package example; public class Work { public void setContext(com.ibm.dse.base.Context c){} public int execute(){return System.currentTimeMillis()>1000?1:0;} }')
    session.boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    bundle.files[0].content=bundle.files[0].content.replace('return 7;','return evaluate(System.currentTimeMillis());').replace('public int unusedHelper(){return 99;}','public int evaluate(long value){return value>1000?1:0;}')
    bundle.files[1].content=bundle.files[1].content.replace('assertEquals(7,new Work().execute())','assertEquals(0,new Work().evaluate(999))')
    session.executable_settings=ExecutableVerificationSettings(mode='executable_boundary_v1',coverage_expansion_rounds=rounds,require_branch_coverage=required)
    session.static(bundle)
    profile=PipelineConfiguration(java_version=25)
    def compare(project,context,validation):session.compare(project,context,bundle,build_validation=validation.model_dump(mode='json'))
    def build():return accept_bundle(tmp_path/'project',validate_bundle(bundle),actual_build,profile,[],
        testing_contract=testing_contract(profile),required_tests=[bundle.files[1].path],pre_publish=compare)
    if rounds==0 and required:
        with pytest.raises(VerificationIncomplete) as error:build()
        assert error.value.verification_feedback['stage']=='coverage'
        assert error.value.verification_feedback['coverage_expansion']['stop_reason']=='disabled'
        assert not (tmp_path/'project'/bundle.files[0].path).exists()
        return
    validation,_=build()
    assert validation['tests_passed'] and validation['test_count']==1
    gaps=[b for b in session.last_report['coverage']['branches'] if b['unexercised_outcomes']]
    assert bool(gaps)==(rounds==0)
    assert session.last_report['coverage_expansion']['additional_cases']>0 if rounds else any('nonblocking' in warning for warning in session.last_report['warnings'])
    conn=get_connection(':memory:');create_all_tables(conn);upsert_run(conn,run_id=config.run_id,run_mode='full_inventory')
    record_verification(conn,config,original['unit_id'],'accepted',session.last_report)
    files={f.path:hashlib.sha256(f.content.encode()).hexdigest() for f in bundle.files}
    require_unit_receipts(conn,config,{'bindings':{'step':{'unit_id':original['unit_id'],'files':files}}})
    conn.close()


def test_nested_context_conditions_reuse_reached_input(boundary_tool,tmp_path):
    original=unit(sources=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),source('work',
        'package example; public class Work { private com.ibm.dse.base.Context context; public void setContext(com.ibm.dse.base.Context c){context=c;} public int execute(){if("OPEN".equals(context.getValueAt("outer"))){if("SPECIAL".equals(context.getValueAt("inner"))){return 2;}return 1;}return 0;} }')])
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    left=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
    right=BoundaryHarnessBinding(adapter_class='fixture.Adapter',sources=[dict(path='fixture/Adapter.java',content=
        'package fixture; public class Adapter implements il.co.dcd.verification.harness.BoundaryAdapter { public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element configuration){if("OPEN".equals(context.get("outer"))){if("SPECIAL".equals(context.get("inner"))){return 2;}return 1;}return 0;} }')])
    expansion=CoverageExpansion(original,boundary,ExecutableVerificationSettings(mode='executable_boundary_v1'),left)
    report=verify_boundary(original,boundary,left,right,[BoundaryCase(case_id='baseline',initial_context={'outer':'closed','inner':'closed'})],
        tmp_path/'nested',tool=boundary_tool,candidate_label='nested_fixture',comparison_policy=VERSION,coverage_expansion=expansion)
    assert report.status=='matched_observed_cases',report.issues
    assert len(expansion.rounds)==2
    assert not [branch for branch in report.coverage['branches'] if branch['unexercised_outcomes']],report.coverage
    assert any(case['case']['initial_context']=={'outer':'OPEN','inner':'SPECIAL'} for case in report.cases)
