"""Logging equivalence is reduced explicitly; business observables stay strict."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from models.boundary_case import BoundaryCase
from models.boundary_observation import BoundaryObservation
from models.boundary_comparison_report import BoundaryComparisonReport
from models.thin_path_comparison_report import ThinPathComparisonReport
from tools.behavior_verification.boundary_logging import LOGGING_POLICY
from tools.behavior_verification.boundary_comparison import compare_boundary_observations
from tools.behavior_verification.thin_path_observations import compare_observable_case
from tools.behavior_verification.thin_path_validation import difference_feedback, require_observed_match


def log(message='NilDecorator error in com.ibm.Original for SME', level=900):
    return dict(target='logging:java.util.logging.Logger.log(java.util.logging.Level, java.lang.String, java.lang.Throwable)',
        receiver='com.ibm.Original', arguments=[{'$logging_level':'WARNING','value':level}, message,
            {'exception_type':'java.lang.NullPointerException','message':'JVM-generated text'}])


def observation(events=(), **values):
    return BoundaryObservation(case_id='case',status='completed',external_calls=list(events),**values)


@pytest.mark.parametrize('detail',['message','input_value','logger','exception','overload','order'])
def test_logging_details_are_diagnostic_without_changing_raw_observations(detail):
    left=observation([log(),log('Second warning')]);right=left.model_copy(deep=True)
    event=right.external_calls[0]
    if detail=='message':event['arguments'][1]='Native formatter warning in com.company.Formatter'
    if detail=='input_value':event['arguments'][1]='NilDecorator error in com.ibm.Original for INTERNET'
    if detail=='logger':event['receiver']='com.company.Formatter'
    if detail=='exception':event['arguments'][2]={'exception_type':'java.lang.IllegalArgumentException','message':'missing channel'}
    if detail=='overload':
        event['target']='logging:java.util.logging.Logger.warning(java.lang.String)'
        event['arguments']=[event['arguments'][1]]
    if detail=='order':right.external_calls.reverse()
    originals=deepcopy((left.model_dump(),right.model_dump()));diagnostics=[]
    assert compare_boundary_observations(left,right,logging_diagnostics=diagnostics)==[]
    assert diagnostics[0]['blocking'] is False
    assert diagnostics[0]['policy_version']==LOGGING_POLICY['version']
    assert diagnostics[0]['legacy'][0]['event']==left.external_calls[0]
    assert diagnostics[0]['native'][0]['event']==right.external_calls[0]
    assert (left.model_dump(),right.model_dump())==originals


@pytest.mark.parametrize('events',[[],[log(),log()],[log(level=1000)]])
def test_missing_extra_or_changed_severity_blocks_with_count_feedback(events):
    differences=compare_boundary_observations(observation([log()]),observation(events))
    assert differences and all(item['path'].startswith('logging.severity_counts.') for item in differences)
    assert all(isinstance(item['legacy'],int) and isinstance(item['native'],int) for item in differences)


@pytest.mark.parametrize('target',['logging:business.warning(java.lang.String)',
    'logging:java.util.logging.Logger.log(java.util.logging.LogRecord)', 'service:sendWarning'])
def test_unrecognized_events_retain_exact_argument_comparison(target):
    left=dict(target=target,arguments=['original']);right=dict(target=target,arguments=['changed'])
    assert compare_boundary_observations(observation([left]),observation([right]))[0]['path']=='external_calls[0].arguments[0]'


def test_unrecognized_severity_stays_strict_and_business_order_does_not_get_normalized():
    invalid=log();invalid['arguments'][0]={'$logging_level':'WARNING','value':'900'}
    assert compare_boundary_observations(observation([invalid]),observation())
    one=dict(target='service:one',arguments=['id']);two=dict(target='service:two',arguments=['id'])
    assert compare_boundary_observations(observation([one,log(),two]),observation([two,log(),one]))
    diagnostics=[]
    assert not compare_boundary_observations(observation([one,log(),two]),observation([log(),one,two]),logging_diagnostics=diagnostics)
    assert diagnostics  # Movement relative to business calls remains visible.


def test_xml_prefix_values_and_escaped_exceptions_remain_blocking():
    left=observation([log()],output='<r xmlns:xsi="urn:x" xsi:nil="true"/>',exception={'type':'OriginalFailure'})
    right=observation([log()],output='<r xmlns:wtc="urn:x" wtc:nil="true"/>',exception={'type':'OtherFailure'})
    paths={d['path'] for d in compare_boundary_observations(left,right,xml_output=True)}
    assert 'output' in paths and 'exception.type' in paths
    assert compare_boundary_observations(observation([log()],context={'id':'SME'}),observation([log()],context={'id':'WEB'}))


def test_logging_diagnostics_never_become_ai_correction_or_comparison_limitations():
    left=observation([log()]);right=observation([log('Different native warning')]);diagnostics=[]
    differences,limits=compare_observable_case(left,right,[],logging_diagnostics=diagnostics)
    assert not differences and not limits and diagnostics
    report=SimpleNamespace(status='matched_observed_cases',issues=[],unexecuted_case_ids=[],limitations=[],
        cases=[dict(case={'initial_context':{'CHANNEL_NAME':None}},legacy=left.model_dump(),native=right.model_dump(),
            differences=differences,logging_diagnostics=diagnostics)])
    require_observed_match(report)
    assert not difference_feedback(report)['failing_cases']
    report.cases[0]['differences']=compare_boundary_observations(left,observation())
    feedback=difference_feedback(report)
    assert 'logging_diagnostics' not in json.dumps(feedback)
    assert 'com.ibm' not in json.dumps(feedback)
    assert feedback['failing_cases'][0]['input']['initial_context']['CHANNEL_NAME'] is None


@pytest.mark.parametrize('thin',[False,True])
def test_both_report_producers_persist_policy_raw_logs_and_separate_diagnostics(tmp_path,monkeypatch,thin):
    from tools.behavior_verification import boundary_verification,thin_path_comparison
    module=thin_path_comparison if thin else boundary_verification
    boundary=SimpleNamespace(unit_id='unit',unit_fingerprint='revision',implementation_class='Formatter',
        source_manifest_hash='source',configuration_hash='config',reachable_slice=True,
        parser_checklist=SimpleNamespace(status='extracted',items=[]))
    left=observation([log()],output='<r/>');right=observation([log('Native warning')],output='<r/>')
    monkeypatch.setattr(module,'boundary_contract',lambda *a:boundary)
    monkeypatch.setattr(module,'compile_boundary_side',lambda *a,**k:{'side':a[4],'hashes':{}})
    monkeypatch.setattr(module,'execute_boundary_case',lambda compiled,*a,**k:left if compiled['side']=='legacy' else right)
    monkeypatch.setattr(module,'verify_compiled_artifacts',lambda *a:None)
    monkeypatch.setattr(module,'boundary_coverage',lambda *a:{})
    unit={'unit_id':'unit','fingerprint':'revision','kind':'response_format'}
    cases=[BoundaryCase(case_id='case')]
    if thin:report=module.compare_thin_boundary(unit,boundary,None,None,cases,tmp_path/'run')
    else:report=module.verify_boundary(unit,boundary,None,None,cases,tmp_path/'run',candidate_label='report_fixture')
    assert report.status=='matched_observed_cases',report.issues
    saved=json.loads((tmp_path/'run'/'boundary-comparison.json').read_text())
    assert saved['logging_comparison_policy']==LOGGING_POLICY
    assert saved['cases'][0]['logging_diagnostics'][0]['blocking'] is False
    assert saved['cases'][0]['legacy']['external_calls']==left.external_calls
    assert saved['cases'][0]['native']['external_calls']==right.external_calls
    assert not saved['cases'][0]['differences']
    if not thin:
        assert next(f for f in saved['cases'][0]['field_results'] if f['field']=='logging')['result']=='matched'


def test_historical_reports_are_not_relabelled_with_new_policy():
    for model in (BoundaryComparisonReport,ThinPathComparisonReport):
        report=model.model_validate(dict(unit_id='unit',source_manifest_hash='source',configuration_hash='config'))
        assert report.logging_comparison_policy=={}


from test_behavior_verification_boundaries import boundary_tool


def test_real_jvm_warning_normalization_and_missing_warning_mutation(boundary_tool,tmp_path):
    from test_typed_boundary_adapter import typed_example,prepared,first
    from tools.behavior_verification.boundaries import build_boundary_report
    from models.unit_verification_boundary import UnitVerificationBoundary
    from tools.behavior_verification.boundary_verification import verify_boundary
    import hashlib
    unit,_,legacy,native=typed_example(boundary_tool)
    work=next(s for s in unit['sources'] if s['identity']=='work')
    work['content']=work['content'].replace('public int execute() {',
        'public int execute() { java.util.logging.Logger.getLogger("com.ibm.Legacy").log('
        'java.util.logging.Level.WARNING,"Legacy warning",new IllegalStateException("legacy details"));')
    work['content_hash']=hashlib.sha256(work['content'].encode()).hexdigest()
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(unit),tool_jar=boundary_tool)))
    warning='java.util.logging.Logger.getLogger("nativefixture.Work").warning("Native warning " + value);'
    native.sources[0].content=native.sources[0].content.replace('return new Result(value);',warning+' return new Result(value);')
    cases=[BoundaryCase(case_id='case',initial_context={'value':'hello'})]
    report=verify_boundary(unit,boundary,legacy,native,cases,tmp_path/'matching',tool=boundary_tool,
        candidate_label='real_jvm_logging_policy_fixture')
    assert report.status=='matched_observed_cases',report.model_dump_json()
    assert report.cases[0]['logging_diagnostics']
    assert report.cases[0]['legacy']['external_calls'][0]['receiver']=='com.ibm.Legacy'
    native.sources[0].content=native.sources[0].content.replace(warning,'')
    failed=verify_boundary(unit,boundary,legacy,native,cases,tmp_path/'missing',tool=boundary_tool,
        candidate_label='deliberately_missing_warning')
    assert failed.status=='differences_found',failed.issues
    assert [d['path'] for d in failed.cases[0]['differences']]==['logging.severity_counts.900']
