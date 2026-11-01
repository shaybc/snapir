"""Unique path/type matching and incomplete state never masquerade as behavioral equality."""
from types import SimpleNamespace
import pytest
from models.native_verification_binding import NativeVerificationBinding
from models.boundary_observation import BoundaryObservation
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tools.behavior_verification.thin_path_binding import auto_bind
from tools.behavior_verification.thin_path_observations import compare_observable_case
from tools.behavior_verification.thin_path_validation import require_observed_match,difference_feedback


def unit():
    return dict(effective_configuration=dict(attributes={'dataName':'Root'},children=[
        dict(attributes={'dataName':'Client_Id'},children=[])]))


def binding():
    return NativeVerificationBinding(owner_type='com.company.generated.Mapper',method_name='unformat')


def inventory(*getters):
    return dict(result_type='DTO',types={'DTO':[dict(name=name,type=kind) for name,kind in getters]})


def test_case_and_separator_normalization_and_explicit_presence_flag():
    result,mapping,limitations=auto_bind(unit(),binding(),inventory(('getCLIENTID','java.lang.String'),('wasClientIdSet','boolean')),
        {'Client_Id':{'string'}})
    assert result.output=='none' and not result.output_getters
    assert result.context_writes[0].getters==['getCLIENTID']
    assert result.context_writes[0].presence_getters==['wasClientIdSet']
    assert mapping[0]['presence_observable'] and not limitations


@pytest.mark.parametrize('getters,status',[
    ([('getClientId','java.lang.String'),('getClient_Id','java.lang.String')],'ambiguous_or_missing_getter'),
    ([('getClientId','int')],'incompatible_or_unknown_type'),
    ([], 'ambiguous_or_missing_getter')])
def test_no_guessing_between_getters_or_types(getters,status):
    result,mapping,limitations=auto_bind(unit(),binding(),inventory(*getters),{'Client_Id':{'string'}})
    assert not result.context_writes and mapping[0]['status']==status and limitations


def test_duplicate_names_use_distinct_paths_and_do_not_guess_legacy_context_keys():
    source=unit();source['effective_configuration']['children']=[dict(attributes={'dataName':parent},children=[
        dict(attributes={'dataName':'Id'},children=[])]) for parent in ['Left','Right']]
    info=dict(result_type='DTO',types={'DTO':[dict(name='getLeft',type='Left'),dict(name='getRight',type='Right'),
        dict(name='getId',type='java.lang.String')], 'Left':[dict(name='getId',type='java.lang.String')],
        'Right':[dict(name='getId',type='java.lang.String')]})
    result,mappings,limits=auto_bind(source,binding(),info,{'Id':{'string'}})
    assert [item['getters'] for item in mappings]==[['getLeft','getId'],['getRight','getId']]
    assert all(item['status']=='legacy_path_not_observable' for item in mappings)
    assert not result.context_writes and len(limits)==2


@pytest.mark.parametrize('present',[False,True])
def test_null_is_not_presence_information(present):
    left=BoundaryObservation(case_id='null',status='completed',context={'Client_Id':None} if present else {})
    right=BoundaryObservation(case_id='null',status='completed',context={'Client_Id':None})
    mapping=[dict(status='bound',path=['Root','Client_Id'],context_key='Client_Id',presence_observable=False)]
    differences,limitations=compare_observable_case(left,right,mapping)
    assert not differences and limitations[0]['kind']=='presence_not_observable'
    report=SimpleNamespace(status='verification_incomplete',issues=[],unexecuted_case_ids=[],limitations=limitations,
        cases=[dict(case={},differences=[],legacy=left.model_dump(),native=right.model_dump())])
    with pytest.raises(VerificationIncomplete):require_observed_match(report)


def test_partial_writes_are_not_equal_or_a_defect_but_exception_types_are_compared():
    left=BoundaryObservation(case_id='throw',status='completed',context={'Value':'written'},
        writes=[dict(key='Value',value='written')],exception={'type':'java.lang.IllegalArgumentException'})
    right=BoundaryObservation(case_id='throw',status='completed',exception={'type':'java.lang.IllegalArgumentException'})
    differences,limits=compare_observable_case(left,right,[])
    assert not differences and limits[0]['kind']=='partial_writes_not_compared'
    right.exception={'type':'java.lang.NullPointerException'}
    differences,_=compare_observable_case(left,right,[])
    assert any(item['path']=='exception.type' for item in differences)


def test_tooling_failures_are_not_behavior_differences():
    left=BoundaryObservation(case_id='incomplete',status='completed')
    right=BoundaryObservation(case_id='incomplete',status='verification_incomplete',issues=['unsupported API'])
    differences,limits=compare_observable_case(left,right,[])
    assert differences==[] and limits[0]['kind']=='execution_incomplete'


def test_feedback_contains_only_inputs_and_compared_differences():
    report=SimpleNamespace(status='differences_found',cases=[dict(case={'input_xml':'<R/>'},
        differences=[dict(path='context.Value',legacy='before',native='after',related_checklist_ids=['check-'+str(i) for i in range(400)])],
        legacy={'probes':['huge']},native={'probes':['huge']})])
    feedback=difference_feedback(report)
    assert feedback['failing_cases'][0]==dict(input={'input_xml':'<R/>'},differences=[dict(path='context.Value',legacy='before',native='after')])


def test_saved_attempt_selection_preserves_earlier_java_and_rejects_stale_sources(tmp_path):
    import sqlite3,json,hashlib
    from tools.behavior_verification.thin_path_saved_candidate import read_candidate
    from tests.runtime.test_behavior_conversion import bundle
    path=tmp_path/'attempts.db';candidate=bundle();original=candidate.files[0].content
    selected=dict(unit_id='selected',fingerprint='revision',sources=[dict(identity='original',content='original source')])
    request=dict(selected_unit={'fingerprint':'revision'},sources=selected['sources'])
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE behavior_attempts(category TEXT,identity TEXT,attempt INTEGER,request_json TEXT,response TEXT)')
        conn.execute('INSERT INTO behavior_attempts VALUES(?,?,?,?,?)',('thin_path_experiment','selected',3,json.dumps(request),candidate.model_dump_json()))
        candidate.files[0].content='later rejected candidate'
        conn.execute('INSERT INTO behavior_attempts VALUES(?,?,?,?,?)',('thin_path_experiment','selected',4,json.dumps(request),candidate.model_dump_json()))
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    saved,metadata=read_candidate(path,3,selected)
    assert saved.files[0].content==original and metadata['generation_performed'] is False
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    selected['sources'][0]['content']='changed source'
    with pytest.raises(ValueError,match='revision differs'):read_candidate(path,3,selected)


def test_shared_retry_loop_stops_on_a_comparison_limitation():
    from tests.runtime.test_behavior_conversion import state,bundle
    from runtime.behavior_conversion.generation import generate
    from models.pipeline_configuration import PipelineConfiguration
    from models.native_unit_bundle import NativeUnitBundle
    conn,config=state();calls=[]
    def model(*args):calls.append(True);return bundle().model_dump_json()
    def validator(*args,**kwargs):raise VerificationIncomplete(dict(stage='tooling',issues=['presence not observable']))
    try:
        with pytest.raises(VerificationIncomplete):
            generate(conn,config,PipelineConfiguration(model_provider='mock',max_agent_task_retries=4),
                'thin_path_experiment','example','Experiment instructions',{},NativeUnitBundle,validator=validator,model_call=model)
        assert len(calls)==1
    finally:conn.close()


def test_real_jvm_getters_presence_partial_state_and_later_cases(boundary_tool,tmp_path):
    from test_behavior_verification_boundaries import source,unit as make_unit,prepared,first
    from test_typed_boundary_adapter import ROOT
    from tools.behavior_verification.boundaries import build_boundary_report
    from tools.behavior_verification.thin_path_comparison import compare_thin_boundary
    from models.unit_verification_boundary import UnitVerificationBoundary
    from models.boundary_harness_binding import BoundaryHarnessBinding
    from models.boundary_case import BoundaryCase
    original=make_unit('request_unformat','example.Formatter',sources=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),
        source('formatter','''package example; import com.ibm.dse.base.Context; public class Formatter {
        public void unformat(String xml,Context context) {
            if(xml.equals("missing"))return;
            context.setValueAt("Value",xml.equals("null")?null:xml);
            if(xml.equals("throw"))throw new IllegalArgumentException();
        }}''')])
    root=original['effective_configuration']['children'][0];root['decorators']=[];root['attributes']={'dataName':'Value'}
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original),tool_jar=boundary_tool)))
    native=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',
        sources=[dict(path='com/company/generated/Request.java',content='''package com.company.generated; public class Request {
        public Result unformat(String xml) {
            if(xml.equals("throw"))throw new IllegalArgumentException();
            return new Result(xml.equals("null")?null:xml,!xml.equals("missing"));
        }
        public static class Result { private final String value;private final boolean present;
            public Result(String value,boolean present){this.value=value;this.present=present;}
            public String getValue(){return value;} public boolean wasValueSet(){return present;}
        }}''')],native_entry=dict(owner_type='com.company.generated.Request',method_name='unformat',
            arguments=[dict(type_name='java.lang.String',source='xml')]))
    cases=[BoundaryCase(case_id=value,input_xml=value) for value in ['hello','missing','null','throw','later']]
    report=compare_thin_boundary(original,boundary,
        BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),native,cases,
        tmp_path/'comparison',tool=boundary_tool)
    assert not report.issues,report.model_dump_json(indent=2)
    assert len(report.cases)==5 and all(case['native']['status']=='completed' for case in report.cases)
    assert report.auto_binding[0]['presence_observable']
    assert all(not case['differences'] for case in report.cases)
    assert report.cases[1]['native']['context']=={} and report.cases[2]['native']['context']=={'Value':None}
    assert report.cases[3]['limitations'][0]['kind']=='partial_writes_not_compared'
    assert report.cases[4]['comparison_status']=='matched'
    assert report.status=='verification_incomplete'


from test_behavior_verification_boundaries import boundary_tool
