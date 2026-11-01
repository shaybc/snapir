"""The thin path skips AI citation tables, but not execution, source guards or observable differences."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.boundary_case import BoundaryCase
from runtime.behavior_conversion.verification_feedback import VerificationFailure
from tools.behavior_verification.thin_path_request import OPERATION, SELECTION, select_units, build_request
from tools.behavior_verification.thin_path_validation import require_observed_match


def preparation():
    units = [dict(kind=kind, logical_id=name, unit_id='id-'+name, configuration_xml='<configured/>',
        effective_configuration={}, referenced_definitions=[], fingerprint='original',
        sources=[dict(identity='source-'+name, content='full original implementation', content_hash='hash')])
        for kind, name in SELECTION]
    units.append(dict(kind='configured_step', logical_id='UnrelatedStoredProcedure'))
    return dict(operations={OPERATION: dict(status='prepared', units=units)})


def test_pro_model_override_reaches_response_only_runner(monkeypatch):
    from tools.behavior_verification import thin_path_run
    calls=[]
    def run(*args,**kwargs):
        calls.append(kwargs)
        return {'status':'matched_observed_cases'}
    monkeypatch.setattr(thin_path_run,'run',run)
    assert thin_path_run.main(['--input-run','original','--output','fresh','--only-unit','StandardErrorRSFmt',
        '--side-road','--model-name','gemini/gemini-3.1-pro-preview'])==0
    assert calls[0]['model_name']=='gemini/gemini-3.1-pro-preview'
    assert calls[0]['only_unit']=='StandardErrorRSFmt' and calls[0]['side_road']
    assert PipelineConfiguration().model_name=='gemini/gemini-3.7-flash'
    assert PipelineConfiguration(model_name='gemini/gemini-3.5-flash-lite').model_name=='gemini/gemini-3.5-flash-lite'


def test_selects_exactly_three_real_units_and_does_not_modify_preparation():
    original = preparation(); before = deepcopy(original)
    units = select_units(original)
    assert [(unit['kind'], unit['logical_id']) for unit in units] == SELECTION
    units[0]['sources'][0]['content'] = 'changed copy'
    assert original == before
    original['operations'][OPERATION]['units'].append(deepcopy(original['operations'][OPERATION]['units'][0]))
    with pytest.raises(ValueError, match='exactly one'):
        select_units(original)


def test_request_supplies_complete_selected_source_without_framework_tasks_or_citation_obligations():
    unit = select_units(preparation())[0]
    boundary = SimpleNamespace(unit_id=unit['unit_id'], source_manifest_hash='source-revision', configuration_hash='xml-revision')
    request, instruction = build_request(unit, boundary, [], PipelineConfiguration(java_version=25))
    assert request['sources'] == unit['sources'] and request['sources'] is not unit['sources']
    assert request['selected_unit']['configuration_xml'] == unit['configuration_xml']
    assert request['coverage_example']['coverage'].keys() == request['requirements'].keys()
    assert 'parser_checklist' not in request and 'components' not in request
    assert 'Do not return executable harness adapters' in instruction
    assert 'Do not return executable harness adapters, expected observations or parser checklist answers/citations' in instruction


def test_request_reaches_shared_generation_without_reintroducing_unit_example():
    from tests.runtime.test_behavior_conversion import state
    from runtime.behavior_conversion.generation import generate
    from models.native_unit_bundle import NativeUnitBundle
    conn, config = state()
    profile = PipelineConfiguration(java_version=25, model_provider='mock')
    unit = select_units(preparation())[0]
    boundary = SimpleNamespace(unit_id=unit['unit_id'], source_manifest_hash='source-revision', configuration_hash='xml-revision')
    request, instruction = build_request(unit, boundary, [], profile)
    called = []
    def model(prompt, encoded):
        called.append(encoded)
        assert '"coverage": {"business"' not in prompt
        raise RuntimeError('model boundary reached')
    try:
        with pytest.raises(RuntimeError, match='model boundary reached'):
            generate(conn, config, profile, 'thin_path_experiment', unit['unit_id'], instruction, request,
                     NativeUnitBundle, model_call=model)
        assert len(called) == 1
    finally:
        conn.close()


@pytest.mark.parametrize('problem', ['different', 'incomplete', 'no_cases', 'unexecuted', 'issues', 'bad_side', 'error_only'])
def test_result_flags_or_error_only_execution_cannot_establish_observed_match(problem):
    case = dict(case={}, differences=[], legacy=dict(status='completed', exception=None), native=dict(status='completed', exception=None))
    report = SimpleNamespace(status='matched_observed_cases', issues=[], unexecuted_case_ids=[], cases=[case])
    if problem=='different': case['differences']=[dict(path='output', legacy='xsi:nil', native='wtc:nil')]
    if problem=='incomplete': report.status='verification_incomplete'
    if problem=='no_cases': report.cases=[]
    if problem=='unexecuted': report.unexecuted_case_ids=['missing']
    if problem=='issues': report.issues=['failed to compile legacy']
    if problem=='bad_side': case['native']['status']='verification_incomplete'
    if problem=='error_only': case['legacy']['exception']=case['native']['exception']={'type':'java.lang.IllegalArgumentException'}
    with pytest.raises(VerificationFailure): require_observed_match(report)


def test_coverage_gaps_are_diagnostic_for_experiment_not_full_acceptance():
    report=SimpleNamespace(status='matched_observed_cases', issues=[], unexecuted_case_ids=[],
        coverage=dict(unresolved_edges=['unresolved'], branches=[dict(unexercised_outcomes=['false'])]),
        cases=[dict(case={}, differences=[], legacy=dict(status='completed', exception=None), native=dict(status='completed', exception=None))])
    require_observed_match(report)


def test_real_jvm_comparison_accepts_matching_fixture_and_rejects_changed_value(boundary_tool, tmp_path):
    from test_typed_boundary_adapter import typed_example
    from tools.behavior_verification.boundary_verification import verify_boundary
    original, boundary, legacy, native = typed_example(boundary_tool)
    cases=[BoundaryCase(case_id='text', initial_context={'value':'hello'})]
    report=verify_boundary(original,boundary,legacy,native,cases,tmp_path/'control',tool=boundary_tool,
        candidate_label='thin_path_trusted_adapter_fixture_not_live_AI')
    require_observed_match(report)
    assert report.artifact_hashes and not report.acceptance_gate_enabled
    native.sources[0].content=native.sources[0].content.replace('return value;', 'return "invented";')
    changed=verify_boundary(original,boundary,legacy,native,cases,tmp_path/'defect',tool=boundary_tool,
        candidate_label='thin_path_deliberate_output_mutation')
    assert changed.status=='differences_found'
    with pytest.raises(VerificationFailure): require_observed_match(changed)


from test_behavior_verification_boundaries import boundary_tool


@pytest.mark.parametrize('candidate_error',[True,False])
def test_junit_candidate_errors_are_not_environment_failures(tmp_path,monkeypatch,candidate_error):
    from tools.behavior_verification import thin_path_validation as module
    from runtime.behavior_conversion.test_feedback import TestCorrectionError
    from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
    error=TestCorrectionError('JUnit failed',{'diagnostics':['assertion failed']}) if candidate_error else OSError('JVM unavailable')
    monkeypatch.setattr(module,'validate_bundle',lambda *a,**k:{})
    monkeypatch.setattr(module,'validate_testing_contract',lambda *a,**k:None)
    monkeypatch.setattr(module,'validate_binding',lambda *a,**k:None)
    monkeypatch.setattr(module,'controlled_cases',lambda *a,**k:[])
    def fail(*a,**k):raise error
    monkeypatch.setattr(module,'accept_bundle',fail)
    validator=module.ThinPathValidator({'unit_id':'unit','kind':'response_format','sources':[]},None,[],
        {'requirements':{},'testing_contract':{}},SimpleNamespace(allowed_ibm_classes=[]),tmp_path,lambda:None)
    bundle=SimpleNamespace(unit_contract=SimpleNamespace(unit_id='unit',apis=[],evidence_ids=[]),
        verification_binding=None,coverage={},dependencies=[],model_dump_json=lambda **k:'{}')
    with pytest.raises(TestCorrectionError if candidate_error else VerificationIncomplete):validator(bundle)
    assert len(list(tmp_path.glob('attempt-*/failure.json')))==1
