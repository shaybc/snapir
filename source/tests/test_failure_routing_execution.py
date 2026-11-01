"""Actual JVM errors identify adapter wiring without blaming reflective business failures."""
from types import SimpleNamespace
import json
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.unit_verification_boundary import UnitVerificationBoundary
from models.boundary_case import BoundaryCase
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.native_verification_binding import NativeVerificationBinding
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.native_metadata import inspect_native
from runtime.behavior_conversion.failure_routing import adapter_failure,AdapterRepairRequired
from runtime.behavior_conversion.adapter_repair import validate_with_adapter_repair
from runtime.behavior_conversion.stage_tasks import StageTasks
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_verification import verify_boundary
from tools.behavior_verification.independent_comparison import VERSION
from test_executable_verification import fixture
from test_behavior_verification_boundaries import boundary_tool,prepared,first
from tests.runtime.test_behavior_conversion import state


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


def test_real_adapter_repair_calls_only_adapter_role_and_preserves_java(boundary_tool,tmp_path):
    original,bundle,_,_=fixture(boundary_tool,tmp_path)
    production=SimpleNamespace(files=[f for f in bundle.files if f.path.startswith('src/main/')])
    before=[f.model_dump_json() for f in production.files]
    inventory=inspect_native(production.files,boundary_tool,original['sources'])
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    correct=bundle.verification_binding.model_copy(deep=True)
    bundle.verification_binding.method_name='missing'
    reports=[];calls=[]
    def validator(value,**kwargs):
        report=verify_boundary(original,boundary,BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),
            BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',sources=production.files,native_entry=value.verification_binding),
            [BoundaryCase(case_id='one')],tmp_path/('comparison'+str(len(reports))),tool=boundary_tool,candidate_label='repair',comparison_policy=VERSION)
        reports.append(report)
        problem=adapter_failure(report)
        if problem:raise AdapterRepairRequired(problem)
        assert report.status=='matched_observed_cases',report.issues
        return report
    def model(prompt,encoded):
        request=json.loads(encoded);calls.append(request)
        assert request['schema']['title']=='NativeExecutableAdapter' and request['adapter_feedback']['stage']=='adapter_invocation'
        return json.dumps({'binding':correct.model_dump(mode='json')})
    conn,config=state()
    profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
    task=StageTasks(conn,config,profile,'unit','revision',model,None)
    try:
        result=validate_with_adapter_repair(task,dict(original,requirements={'r':'Preserve'}),production,inventory,bundle,validator,lambda binding:None)
        assert result.status=='matched_observed_cases' and len(reports)==2 and len(calls)==1
        assert reports[0].cases[0]['native']['failure_origin']=='adapter_binding'
        assert before==[f.model_dump_json() for f in production.files]
        row=conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='adapter'").fetchone()
        assert row[0]==1
        assert not conn.execute("SELECT 1 FROM staged_conversion_tasks WHERE stage='implementation'").fetchone()
    finally:conn.close()


def test_business_reflection_exception_is_not_an_adapter_repair(boundary_tool,tmp_path):
    original,bundle,_,_=fixture(boundary_tool,tmp_path)
    sources=[f.model_copy(deep=True) for f in bundle.files if f.path.startswith('src/main/')]
    sources[0].content=sources[0].content.replace('public int execute(){return 7;}','public int execute() throws Exception {throw new NoSuchMethodException("business");}')
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    report=verify_boundary(original,boundary,BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),
        BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',sources=sources,native_entry=bundle.verification_binding),
        [BoundaryCase(case_id='business')],tmp_path/'business',tool=boundary_tool,candidate_label='business',comparison_policy=VERSION)
    assert report.status=='verification_incomplete'
    assert report.cases[0]['native']['failure_origin'] is None and adapter_failure(report) is None
