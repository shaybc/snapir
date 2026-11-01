"""Only completed, limitation-free mutation differences can stop the case loop early."""
from types import SimpleNamespace
import pytest
from models.boundary_case import BoundaryCase
from models.boundary_observation import BoundaryObservation
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.boundary_verification import verify_boundary
from tools.behavior_verification.independent_comparison import VERSION
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first
from models.unit_verification_boundary import UnitVerificationBoundary
from tools.behavior_verification.boundaries import build_boundary_report
from test_typed_boundary_adapter import ROOT


@pytest.mark.parametrize('stop,count',[(False,2),(True,1)])
def test_real_difference_stops_only_when_explicitly_enabled(boundary_tool,tmp_path,stop,count):
    original=unit(sources=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),
        source('work','package example; public class Work { public void setContext(com.ibm.dse.base.Context c){} public int execute(){return 7;} }')])
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    left=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
    right=BoundaryHarnessBinding(adapter_class='fixture.Adapter',sources=[dict(path='fixture/Adapter.java',content=
        'package fixture; public class Adapter implements il.co.dcd.verification.harness.BoundaryAdapter { public Object invoke(String xml,java.util.Map<String,Object> context,org.w3c.dom.Element configuration){return 8;} }')])
    with java_scope(PipelineConfiguration(java_version=25)):
        report=verify_boundary(original,boundary,left,right,[BoundaryCase(case_id='first'),BoundaryCase(case_id='second')],
            tmp_path/'comparison',tool=boundary_tool,candidate_label='deliberate_mutant_fixture',comparison_policy=VERSION,stop_after_difference=stop)
    assert report.status=='differences_found',report.issues
    assert len(report.cases)==count
    assert report.unexecuted_case_ids==(['second'] if stop else [])
    assert report.execution_environment['case_timeout_seconds']==15
    assert (report.execution_environment.get('stopping_reason')=='completed_observable_difference')==stop


def test_limitation_bearing_difference_does_not_stop_and_keeps_per_case_timeout(tmp_path,monkeypatch):
    from tools.behavior_verification import boundary_verification as module
    original=unit();boundary=boundary_contract(original)
    boundary.reachable_slice=SimpleNamespace(nodes=[],edges=[])
    boundary.parser_checklist=SimpleNamespace(status='extracted',items=[])
    timeouts=[]
    monkeypatch.setattr('tools.behavior_verification.comparison_environment.runtime_fingerprint',lambda:'environment')
    monkeypatch.setattr(module,'compile_boundary_side',lambda *a,**kw:dict(side=a[4],hashes={}))
    monkeypatch.setattr(module,'verify_compiled_artifacts',lambda *a:None)
    def execute(compiled,u,b,binding,case,**options):
        timeouts.append(options['timeout'])
        return BoundaryObservation(case_id=case.case_id,status='completed',output=7)
    monkeypatch.setattr(module,'execute_boundary_case',execute)
    monkeypatch.setattr('tools.behavior_verification.independent_comparison.compare_case',lambda *a,**kw:
        dict(comparison_status='different',differences=[dict(path='output',expected=7,actual=8)],
             limitations=[dict(kind='presence_not_observable')],logging_diagnostics=[],field_results=[]))
    binding=BoundaryHarnessBinding(adapter_class='fixture.Adapter')
    report=verify_boundary(original,boundary,binding,binding,[BoundaryCase(case_id='first'),BoundaryCase(case_id='second')],
        tmp_path/'comparison',candidate_label='limited_mutation_fixture',comparison_policy=VERSION,stop_after_difference=True)
    assert len(report.cases)==2 and not report.unexecuted_case_ids
    assert timeouts==[15,15,15,15]
    assert 'stopping_reason' not in report.execution_environment
