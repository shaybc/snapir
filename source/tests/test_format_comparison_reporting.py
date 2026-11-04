"""Diagnostic comparisons retain uncertainty without counting framework events as behavior."""
from models.boundary_observation import BoundaryObservation
from models.format_comparison_settings import FormatComparisonSettings
from runtime.format_comparison.reporting import compare_case, publish


def obs(**kwargs):
    return BoundaryObservation(case_id='case', status='completed', **kwargs)


def test_final_values_match_despite_different_internal_write_events():
    a = obs(context={'flag': False}, writes=[dict(key='flag', value=False)])
    b = obs(context={'flag': False})
    assert compare_case(a, b, 'unformat', FormatComparisonSettings())['status'] == 'matched'
    assert compare_case(a, obs(context={}), 'unformat', FormatComparisonSettings())['status'] == 'different'


def test_xml_text_is_not_trimmed_and_invalid_xml_is_visible():
    settings = FormatComparisonSettings()
    assert compare_case(obs(output='<v> true </v>'), obs(output='<v>true</v>'), 'format', settings)['status'] == 'different'
    result = compare_case(obs(output='<>bad</>'), obs(output='<>bad</>'), 'format', settings)
    assert result['xml_exact_match'] and result['xml_valid'] is False
    assert result['status'] == 'comparison_unavailable'


def test_unavailable_adapter_never_counts_as_a_match(tmp_path):
    incomplete = BoundaryObservation(case_id='case', status='verification_incomplete', issues=['Missing input binding'])
    result = compare_case(incomplete, incomplete, 'format', FormatComparisonSettings())
    assert result['status'] == 'comparison_unavailable'
    report = dict(label='test', planned_cases=2, cases=[dict(case={'case_id': 'case'}, **result)])
    publish(report, tmp_path)
    assert report['counts']['matched'] == 0 and report['counts']['unexecuted'] == 1


def test_format_business_exceptions_match_without_type_message_or_implicit_state_requirements():
    a = obs(exception={'type': 'java.lang.IllegalArgumentException', 'message': 'original'})
    b = obs(exception={'type': 'nativecode.ValidationException', 'message': 'native'}, context={'temporary': 'value'})
    for direction in ['format', 'unformat']:
        for settings in [FormatComparisonSettings(), FormatComparisonSettings(compare_exception_messages=True)]:
            result = compare_case(a, b, direction, settings)
            assert result['status'] == 'matched'
            assert result['differences'] == [] and result['limitations'] == []
    assert a.exception['type'] == 'java.lang.IllegalArgumentException'
    assert b.exception['type'] == 'nativecode.ValidationException'
    changed = compare_case(a, obs(output=False), 'unformat', FormatComparisonSettings())
    assert changed['status'] == 'different'


def test_exception_matching_keeps_declared_state_resource_and_adapter_checks():
    a = obs(exception={'type': 'ibm.BusinessException'}, context={'value': 1})
    b = obs(exception={'type': 'nativecode.BusinessException'}, context={'value': 2})
    assert compare_case(a, b, 'format', FormatComparisonSettings(), observe_context_keys=['value'])['status'] == 'different'
    assert compare_case(a, b, 'format', FormatComparisonSettings(), observe_context_keys=[])['status'] == 'matched'
    incomplete = obs(exception={'type': 'HarnessError'}, failure_origin='adapter_binding', issues=['Missing fixture'])
    assert compare_case(a, incomplete, 'format', FormatComparisonSettings())['status'] == 'comparison_unavailable'
    a.resource_events = [{'operation': 'commit'}]
    assert compare_case(a, b, 'format', FormatComparisonSettings())['status'] == 'different'


def test_operation_step_exception_policy_is_unchanged():
    a = obs(exception={'type': 'original.Exception', 'message': 'original'})
    b = obs(exception={'type': 'original.Exception', 'message': 'native'})
    assert compare_case(a, b, 'step_execute', FormatComparisonSettings())['status'] == 'comparison_unavailable'
    strict = compare_case(a, b, 'step_execute', FormatComparisonSettings(compare_exception_messages=True))
    assert strict['status'] == 'different' and strict['differences'][0]['path'] == 'exception.message'
    b.exception['type'] = 'different.Exception'
    assert compare_case(a, b, 'step_execute', FormatComparisonSettings())['status'] == 'different'


def test_a_branch_decision_does_not_prove_the_targeted_outcome():
    from models.format_comparison_case import FormatComparisonCase
    from runtime.format_comparison.reporting import branch_results
    case = FormatComparisonCase(case_id='branch', binding_id='write', targeted_branch_ids=['if-channel'],
                                targeted_branch_outcomes={'if-channel': 'true'})
    assert branch_results(case, [{'id': 'if-channel', 'outcome': 'false'}])['if-channel']['status'] == 'targeted_not_confirmed'
    assert branch_results(case, [{'id': 'if-channel', 'outcome': 'true'}])['if-channel']['status'] == 'observed'
    case.targeted_branch_outcomes = {}
    assert branch_results(case, [{'id': 'if-channel', 'outcome': 'true'}])['if-channel']['status'] == 'targeted_not_confirmed'

