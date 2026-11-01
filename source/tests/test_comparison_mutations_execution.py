"""Deliberate native mutations exercise the same independent comparison as acceptance."""
import hashlib
import json
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.unit_verification_boundary import UnitVerificationBoundary
from models.boundary_case import BoundaryCase
from models.boundary_harness_binding import BoundaryHarnessBinding
from runtime.java_toolchain import java_scope
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.comparison_mutations import measure
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first
from test_typed_boundary_adapter import ROOT


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


def job(tool,original,native,cases,limit=4):
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=tool)))
    return dict(unit=original,boundary=boundary.model_dump(mode='json'),native=native.model_dump(mode='json'),
        legacy=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter').model_dump(mode='json'),
        cases=[case.model_dump(mode='json') for case in cases],tool=str(tool),max_mutants=limit,
        candidate_sources={file.path:hashlib.sha256(file.content.encode()).hexdigest() for file in native.sources})


def test_prefix_mutation_detected_and_unused_method_uncovered(boundary_tool,tmp_path):
    value='<Value xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"/>'
    original=unit('response_format','example.Formatter',[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),
        source('formatter','package example; public class Formatter { public String format(com.ibm.dse.base.Context c){return '+json.dumps(value)+';} }')])
    original['effective_configuration']['children'][0]['decorators']=[]
    native=BoundaryHarnessBinding(adapter_class='fixture.Adapter',sources=[dict(path='fixture/Adapter.java',content=
        'package fixture; public class Adapter implements il.co.dcd.verification.harness.BoundaryAdapter { public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element configuration){return '+json.dumps(value)+';} public int unused(){return 0;} }')])
    before=native.model_dump_json()
    report=measure(job(boundary_tool,original,native,[BoundaryCase(case_id='nil')]),tmp_path)
    assert report['baseline_status']=='matched_observed_cases',report
    assert report['status']=='completed' and report['counts']['detected']==1 and report['counts']['uncovered']==1,report
    assert native.model_dump_json()==before


def test_removed_write_condition_and_return_mutations(boundary_tool,tmp_path):
    original=unit(sources=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),source('work',
        'package example; public class Work { private com.ibm.dse.base.Context c; public void setContext(com.ibm.dse.base.Context value){c=value;} public int execute(){c.setValueAt("answer", "yes");if(c.getValueAt("flag")==null){return 1;}return 0;} }')])
    native=BoundaryHarnessBinding(adapter_class='fixture.Adapter',sources=[dict(path='fixture/Adapter.java',content=
        'package fixture; public class Adapter implements il.co.dcd.verification.harness.BoundaryAdapter { public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element configuration){context.put("answer", "yes");if(context.get("flag")==null){return 1;}return 0;} }')])
    report=measure(job(boundary_tool,original,native,[BoundaryCase(case_id='missing'),BoundaryCase(case_id='value',initial_context={'flag':'x'})],8),tmp_path)
    assert report['baseline_status']=='matched_observed_cases',report
    by_kind={kind:[entry for entry in report['mutations'] if entry['kind']==kind] for kind in ('removed_write','negated_condition','changed_return')}
    assert all(entries and all(entry['status']=='detected' for entry in entries) for entries in by_kind.values()),report
    assert sum(report['counts'].values())<=8


def test_unchanged_baseline_failure_stops_mutations(boundary_tool,tmp_path):
    from test_executable_verification import fixture
    original,bundle,_,_=fixture(boundary_tool,tmp_path,value=8)
    native=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',native_entry=bundle.verification_binding,
        sources=[file for file in bundle.files if file.path.startswith('src/main/')])
    report=measure(job(boundary_tool,original,native,[BoundaryCase(case_id='baseline')]),tmp_path)
    assert report['status']=='baseline_not_verified' and not report['mutations']
    assert not (tmp_path/'mutation-plans.xml').exists()


@pytest.mark.parametrize('body,value,expected',[
    ('if(context.containsKey("flag")){return 7;}return 7;',7,'survived'),
    ('switch(xml){case "a":return 1;default:return 0;}',0,'invalid')])
def test_real_survivors_and_invalid_mutations_are_separate(boundary_tool,tmp_path,body,value,expected):
    original=unit(sources=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),source('work',
        'package example; public class Work { public void setContext(com.ibm.dse.base.Context c){} public int execute(){return '+str(value)+';} }')])
    native=BoundaryHarnessBinding(adapter_class='fixture.Adapter',sources=[dict(path='fixture/Adapter.java',content=
        'package fixture; public class Adapter implements il.co.dcd.verification.harness.BoundaryAdapter { public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element configuration){'+body+'} }')])
    report=measure(job(boundary_tool,original,native,[BoundaryCase(case_id='baseline',input_xml='b')],1),tmp_path)
    assert report['baseline_status']=='matched_observed_cases',report
    assert report['counts'][expected]==1,report


def test_enabled_measurement_survives_real_build_and_keeps_candidate(boundary_tool,tmp_path):
    from test_executable_verification import fixture
    from tests.runtime.test_scoped_native import actual_build
    from runtime.behavior_conversion.bundle_output import accept_bundle,validate_bundle
    from runtime.behavior_conversion.testing_contract import testing_contract
    from runtime.behavior_conversion.verification_state import record_verification
    from tools.state_store_tools.db import get_connection,create_all_tables
    from tools.state_store_tools.runs import upsert_run
    original,bundle,config,session=fixture(boundary_tool,tmp_path)
    before=bundle.model_dump_json()
    session.executable_settings.comparison_mutations.enabled=True
    session.static(bundle)
    profile=PipelineConfiguration(java_version=25)
    def compare(project,context,validation):session.compare(project,context,bundle,build_validation=validation.model_dump(mode='json'))
    validation,_=accept_bundle(tmp_path/'project',validate_bundle(bundle),actual_build,profile,[],
        testing_contract=testing_contract(profile),required_tests=[bundle.files[1].path],pre_publish=compare)
    assert validation['tests_passed'] and validation['test_count']==1
    result=session.last_report['comparison_strength']
    assert result['status']=='completed',json.loads(open(result['evidence'],encoding='utf-8').read())
    assert json.loads(open(result['evidence'],encoding='utf-8').read())['baseline_reused']
    assert result['counts']['detected']==1 and result['counts']['uncovered']==1
    assert bundle.model_dump_json()==before
    assert (tmp_path/'project'/bundle.files[0].path).read_text(encoding='utf-8')==bundle.files[0].content
    conn=get_connection(':memory:');create_all_tables(conn);upsert_run(conn,run_id=config.run_id,run_mode='full_inventory')
    record_verification(conn,config,original['unit_id'],'accepted',session.last_report)
    conn.close()
