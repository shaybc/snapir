"""Compiled counterexamples prove the comparison gate independently of generated JUnit assertions."""
from copy import deepcopy
import json
import pytest
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.boundary_case import BoundaryCase
from models.pipeline_configuration import PipelineConfiguration
from models.unit_verification_boundary import UnitVerificationBoundary
from runtime.java_toolchain import java_scope
from tools.behavior_verification.independent_comparison import VERSION
from tools.behavior_verification.boundary_verification import verify_boundary
from tools.behavior_verification.boundaries import build_boundary_report
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first
from test_boundary_harness import controlled_unit


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


@pytest.mark.parametrize('defect,path',[
    ('output','output'),('write','context.balance'),('external_call','external_calls.length')])
def test_real_output_write_and_call_defects_are_detected(boundary_tool,tmp_path,defect,path):
    original,boundary,left,right,cases=controlled_unit(boundary_tool)
    before=right.model_dump_json();changed=right.model_copy(deep=True)
    code=changed.sources[0].content
    if defect=='output':code=code.replace('return 0;','return 1;')
    elif defect=='write':code=code.replace('context.put("balance", External.balance("client"));','String discardedBalance=External.balance("client");')
    else:code=code.replace('External.code(1)','7')
    changed.sources[0].content=code
    report=verify_boundary(original,boundary,left,changed,cases[:1],tmp_path/defect,tool=boundary_tool,
        candidate_label='deliberate_fixture_defect',comparison_policy=VERSION)
    assert report.status=='differences_found',report.model_dump_json(indent=2)
    assert path in {delta['path'] for delta in report.cases[0]['differences']}
    assert report.execution_environment['comparison_summary']['different']==1
    if defect=='external_call':
        assert report.cases[0]['native']['invocation_completed'] is True
        assert report.cases[0]['limitations'] and report.execution_environment['comparison_summary']['cases_with_limitations']==1
    assert right.model_dump_json()==before


def test_real_xml_prefix_defect_is_not_normalized_away(boundary_tool,tmp_path):
    original,_,left,_,_=controlled_unit(boundary_tool)
    nil='<Value xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"/>'
    literal=json.dumps(nil)
    formatter='package example; public class Formatter { public String format(com.ibm.dse.base.Context context){ return '+literal+'; } }'
    original=unit('response_format','example.Formatter',[item for item in original['sources'] if item['identity'] in {'context','tag'}]+[source('formatter',formatter)])
    original['effective_configuration']['children'][0]['decorators']=[]
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    code='package fixture; public class Response implements il.co.dcd.verification.harness.BoundaryAdapter { public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element configuration){return '+literal.replace('xsi','wtc')+';} }'
    right=BoundaryHarnessBinding(adapter_class='fixture.Response',sources=[dict(path='fixture/Response.java',content=code)])
    report=verify_boundary(original,boundary,left,right,[BoundaryCase(case_id='prefix')],tmp_path/'prefix',tool=boundary_tool,
        candidate_label='deliberate_prefix_defect',comparison_policy=VERSION)
    assert report.status=='differences_found',report.model_dump_json(indent=2)
    assert report.cases[0]['field_results'][0]['result']=='different'
