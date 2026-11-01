"""Separate genuine observable differences from missing comparison capability."""
from types import SimpleNamespace
from copy import deepcopy
import pytest
from models.boundary_observation import BoundaryObservation
from models.boundary_case import BoundaryCase
from models.boundary_comparison_report import BoundaryComparisonReport
from models.native_verification_binding import NativeVerificationBinding
from tools.behavior_verification.independent_comparison import VERSION,compare_case,finish_report
from tools.behavior_verification.boundary_logging import LOGGING_POLICY
from runtime.behavior_conversion.verification_feedback import comparison_feedback


def observed(**values):return BoundaryObservation(case_id='case',status='completed',**values)
def projection(presence=False):
    return NativeVerificationBinding(owner_type='native.Step',method_name='execute',context_writes=[dict(
        context_key='value',getters=['getValue'],presence_getters=['wasSet'] if presence else [])])


@pytest.mark.parametrize('left,right,path',[
    ({'output':7},{'output':8},'output'),
    ({'context':{'value':'x'},'writes':[{'key':'value','value':'x'}]},{},'context.value'),
    ({'removals':[{'key':'old','value':'x'}]},{'context':{'old':'x'}},'removals.length'),
    ({'external_calls':[{'target':'lookup','arguments':['id']}]},{},'external_calls.length'),
    ({'exception':{'type':'java.lang.IllegalArgumentException'}},{'exception':{'type':'java.lang.IllegalStateException'}},'exception.type'),
])
def test_independent_observable_defects_are_real_differences(left,right,path):
    result=compare_case('case',observed(**left),observed(**right))
    assert result['comparison_status']=='different' and not result['limitations']
    assert path in {d['path'] for d in result['differences']}


def test_prefix_and_empty_null_differences_survive_comparison():
    nil='<Value xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"/>'
    result=compare_case('case',observed(output=nil),observed(output=nil.replace('xsi','wtc')),xml_output=True)
    assert result['comparison_status']=='different'
    assert compare_case('case',observed(output=None),observed(output=''))['comparison_status']=='different'


@pytest.mark.parametrize('present',[True,False])
def test_getters_without_presence_cannot_claim_equality(present):
    left=observed(context={'value':None} if present else {})
    right=observed(context={'value':None},writes=[{'key':'value','value':None}])
    before=(left.model_dump(),right.model_dump())
    result=compare_case('case',left,right,projection())
    assert result['comparison_status']=='incomplete' and not result['differences']
    field=next(f for f in result['field_results'] if f['field']=='context.value')
    assert field['result']=='not_compared' and field['presence_result']=='not_compared'
    assert (left.model_dump(),right.model_dump())==before


def test_known_value_difference_can_be_corrected_without_turning_presence_into_a_repair_request():
    left=observed(context={'value':None},writes=[{'key':'value','value':None}])
    right=observed(context={'value':''},writes=[{'key':'value','value':''}])
    result=compare_case('case',left,right,projection())
    report=BoundaryComparisonReport(unit_id='u',source_manifest_hash='s',configuration_hash='c',
        execution_environment={'comparison_policy':VERSION},cases=[dict(case=BoundaryCase(case_id='case').model_dump(mode='json'),
            legacy=left.model_dump(mode='json'),native=right.model_dump(mode='json'),**result)])
    finish_report(report);feedback=comparison_feedback(report)
    assert report.status=='differences_found' and result['limitations']
    assert feedback['failing_cases'][0]['differences'][0]['path']=='context.value'
    assert 'incomplete_cases' not in feedback
    right.context['value']=None
    report.cases[0].update(compare_case('case',left,right,projection()))
    finish_report(report)
    assert report.status=='verification_incomplete' and not comparison_feedback(report)['failing_cases']


@pytest.mark.parametrize('event',['writes','removals'])
def test_partial_error_state_is_not_a_match_or_a_code_defect(event):
    left=observed(exception={'type':'java.lang.IllegalArgumentException'},**{event:[{'key':'value','value':'x'}]})
    right=observed(exception={'type':'java.lang.IllegalArgumentException'})
    result=compare_case('case',left,right,projection(True))
    assert result['comparison_status']=='incomplete' and not result['differences']
    assert any(l['kind']=='partial_writes_not_compared' for l in result['limitations'])


def test_dto_projection_cannot_prove_repeated_write_or_removal_events():
    repeated=observed(context={'value':'x'},writes=[{'key':'value','value':'first'},{'key':'value','value':'x'}])
    final=observed(context={'value':'x'},writes=[{'key':'value','value':'x'}])
    assert compare_case('case',repeated,final,projection(True))['limitations'][0]['kind']=='write_trace_not_observable'
    removed=observed(removals=[{'key':'old','value':'x'}])
    result=compare_case('case',removed,observed(context={'old':'x'}),projection(True))
    assert result['comparison_status']=='incomplete' and not result['differences']


def test_observation_identity_and_shape_fail_as_tooling_limitations():
    wrong=observed();wrong.case_id='other'
    assert compare_case('case',observed(),wrong)['limitations'][0]['kind']=='observation_identity_mismatch'
    assert compare_case('case',observed(writes=[{'value':1}]),observed())['comparison_status']=='incomplete'


def test_completed_call_trace_survives_failed_control_validation_without_becoming_acceptance():
    calls=[{'target':'one','arguments':[]},{'target':'two','arguments':[]}]
    left=observed(external_calls=calls,invocation_completed=True)
    right=BoundaryObservation(case_id='case',status='verification_incomplete',invocation_completed=True,
        external_calls=calls[:1],issues=['Unused external replay response'])
    result=compare_case('case',left,right)
    assert result['comparison_status']=='different' and result['limitations']
    assert result['differences'][0]['path']=='external_calls.length'
    right.invocation_completed=False
    assert not compare_case('case',left,right)['differences']


def test_all_prepared_cases_run_and_feedback_separates_incomplete_cases(monkeypatch,tmp_path):
    from test_behavior_verification_boundaries import unit
    from tools.behavior_verification.boundary_contracts import boundary_contract
    from tools.behavior_verification.boundary_verification import verify_boundary
    from models.boundary_harness_binding import BoundaryHarnessBinding
    original=unit();contract=boundary_contract(original)
    boundary=SimpleNamespace(unit_id=contract.unit_id,unit_fingerprint=contract.unit_fingerprint,
        source_manifest_hash=contract.source_manifest_hash,configuration_hash=contract.configuration_hash,
        implementation_class=contract.implementation_class,reachable_slice=object(),parser_checklist=SimpleNamespace(status='extracted',items=[]))
    calls=[]
    def compile_side(unit,boundary,binding,directory,side,*args,**kwargs):return dict(side=side,hashes={'tool':'fixture'})
    def execute(compiled,unit,boundary,binding,case,**kwargs):
        calls.append((compiled['side'],case.model_dump()))
        if compiled['side']=='native' and case.case_id=='one':return BoundaryObservation(case_id='one',status='verification_incomplete',issues=['unsupported tool'])
        return BoundaryObservation(case_id=case.case_id,status='completed',output=1 if compiled['side']=='native' and case.case_id=='two' else 0)
    monkeypatch.setattr('tools.behavior_verification.boundary_verification.compile_boundary_side',compile_side)
    monkeypatch.setattr('tools.behavior_verification.boundary_verification.execute_boundary_case',execute)
    monkeypatch.setattr('tools.behavior_verification.boundary_verification.verify_compiled_artifacts',lambda *args:None)
    monkeypatch.setattr('tools.behavior_verification.boundary_verification.boundary_coverage',lambda *args:{})
    binding=BoundaryHarnessBinding(adapter_class='fixture.Adapter')
    report=verify_boundary(original,boundary,binding,binding,[BoundaryCase(case_id=name) for name in ('one','two','three')],
        tmp_path/'mixed',candidate_label='flow_fixture',comparison_policy=VERSION)
    assert len(calls)==6 and all(calls[i][1]==calls[i+1][1] for i in range(0,6,2))
    assert report.status=='differences_found' and not report.unexecuted_case_ids
    assert report.execution_environment['comparison_summary']==dict(matched=1,different=1,incomplete=1,cases_with_limitations=1,unexecuted=0)
    feedback=comparison_feedback(report)
    assert [c['case']['case_id'] for c in feedback['failing_cases']]==['two']
    assert 'legacy' not in feedback['failing_cases'][0]
    assert all('related_checklist_ids' not in delta for delta in feedback['failing_cases'][0]['differences'])
    assert 'incomplete_cases' not in feedback and feedback['correction_scope']=='compared_observable_differences_only'
    report.issues.append('Compiled evidence changed')
    finish_report(report)
    assert report.status=='verification_incomplete' and not comparison_feedback(report)['failing_cases']


def test_receipt_recomputes_actual_observations_instead_of_trusting_match_labels():
    from runtime.behavior_conversion.comparison_receipts import require_observed_agreement
    entry=projection(True).model_copy(update={'context_writes':[]})
    left,right=observed(output=7,invocation_completed=True),observed(output=7,invocation_completed=True)
    record=dict(case=BoundaryCase(case_id='case').model_dump(mode='json'),legacy=left.model_dump(mode='json'),native=right.model_dump(mode='json'),
        **compare_case('case',left,right,entry))
    report=BoundaryComparisonReport(unit_id='u',source_manifest_hash='s',configuration_hash='c',cases=[record],
        logging_comparison_policy=deepcopy(LOGGING_POLICY),execution_environment={'comparison_policy':VERSION})
    finish_report(report)
    receipt=dict(binding=entry.model_dump(mode='json'),comparison_summary=report.execution_environment['comparison_summary'])
    structure=dict(comparison_policy=VERSION,kind='configured_step')
    require_observed_agreement(structure,receipt,report)
    report.cases[0]['native']['invocation_completed']=False
    with pytest.raises(ValueError,match='invocation'):require_observed_agreement(structure,receipt,report)
    report.cases[0]['native']['invocation_completed']=True
    report.cases[0]['native']['output']=8
    with pytest.raises(ValueError,match='do not establish'):require_observed_agreement(structure,receipt,report)
