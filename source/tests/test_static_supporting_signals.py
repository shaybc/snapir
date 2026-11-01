"""Paired-output signals retain literal prefixes, order and revision provenance."""
from copy import deepcopy
import hashlib
import pytest
from models.boundary_comparison_report import BoundaryComparisonReport
from models.unit_static_check_report import UnitStaticCheckReport
from tools.behavior_verification.static_comparison_evidence import comparison_cases
from tools.behavior_verification.supporting_static_checks import supporting_checks
from test_behavior_static_checks import analyze, check, NATIVE
from test_behavior_verification_boundaries import boundary_tool


def observed_report(boundary, files=NATIVE, *, left='<Value/>', right='<Value/>'):
    """Synthetic trusted-harness input, not proof that the fixture's candidate was executed."""
    observation = dict(case_id='fixture-case', status='completed', output=left, context={}, probes=[])
    return BoundaryComparisonReport(unit_id=boundary.unit_id, source_manifest_hash=boundary.source_manifest_hash,
        configuration_hash=boundary.configuration_hash, status='matched_observed_cases',
        artifact_hashes={'native:compiled_text:' + file['path']: hashlib.sha256(file['content'].encode()).hexdigest() for file in files},
        cases=[dict(case=dict(case_id='fixture-case', initial_context={'value': None}), legacy=observation,
                    native={**observation, 'output': right})])


def test_matching_samples_never_authorize_an_exclusion(boundary_tool):
    from test_behavior_static_checks import answer_for
    data = analyze(boundary_tool)
    live = next(item for item in data[1].parser_checklist.items if item.properties.get('value') == '7')
    answer_for(data[2], live.id, status='not_applicable', reason='other_direction')
    report = check(data, boundary_tool, comparison_report=observed_report(data[1]))
    assert report.status == 'mapping_invalid'
    assert live.id in {error.get('checklist_id') for error in report.errors}


def test_unrelated_candidate_report_is_rejected(boundary_tool):
    data = analyze(boundary_tool)
    observed = observed_report(data[1])
    observed.artifact_hashes['native:compiled_text:' + NATIVE[0]['path']] = 'stale'
    report = check(data, boundary_tool, comparison_report=observed)
    assert report.status == 'mapping_invalid'
    assert 'candidate sources' in report.errors[0]['message']


@pytest.mark.parametrize('left,right', [
    ('<R xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><V xsi:nil="true"/></R>',
     '<R xmlns:wtc="http://www.w3.org/2001/XMLSchema-instance"><V wtc:nil="true"/></R>'),
    ('<R><A/><B/></R>', '<R><B/><A/></R>'),
    ('<R><V> </V></R>', '<R><V/></R>'),
    ('<R xmlns="urn:one"/>', '<R xmlns="urn:two"/>'),
    ('<R><V/></R>', '<R/>'),
])
def test_xml_differences_warn_and_supply_exact_case_without_static_rejection(boundary_tool, left, right):
    data = analyze(boundary_tool)
    boundary = data[1].model_copy(update={'kind': 'response_format'})
    report = UnitStaticCheckReport(unit_id=boundary.unit_id, source_manifest_hash=boundary.source_manifest_hash,
                                  configuration_hash=boundary.configuration_hash)
    cases = comparison_cases(observed_report(boundary, left=left, right=right), boundary,
                             {file['path']: file['content'] for file in NATIVE})
    supporting_checks({'kind': 'response_format'}, boundary, {}, set(item.id for item in boundary.parser_checklist.items), cases, report)
    assert report.xml_checks[0]['status'] == 'observed_difference'
    key = report.comparison_requests[0]['case_ids'][0]
    assert report.comparison_cases[key]['case_id'] == 'fixture-case'
    assert not report.errors and report.behavioral_verification == 'not_decided'


def test_xml_attribute_order_alone_does_not_warn(boundary_tool):
    data = analyze(boundary_tool)
    boundary = data[1]
    report = UnitStaticCheckReport(unit_id=boundary.unit_id, source_manifest_hash=boundary.source_manifest_hash,
                                  configuration_hash=boundary.configuration_hash)
    observed = observed_report(boundary, left='<R a="1" b="2"/>', right='<R b="2" a="1"/>')
    supporting_checks({'kind': 'response_format'}, boundary, {}, set(item.id for item in boundary.parser_checklist.items), observed.cases, report)
    assert report.xml_checks[0]['status'] == 'observed_match' and not report.warnings


def test_comment_or_test_only_literal_still_warns(boundary_tool):
    data = analyze(boundary_tool, 'package example; public class Work { public int execute() { String key="xsi:nil"; return 0; } }')
    files = deepcopy(NATIVE)
    files[0]['content'] += '\n// xsi:nil\n'
    files.append(dict(path='src/test/java/nativecode/WorkTest.java', content='package nativecode; class WorkTest { String expected="xsi:nil"; }'))
    report = check(data, boundary_tool, files=files)
    literal = next(value for value in report.literal_checks if value['value'] == 'xsi:nil')
    assert literal['status'] == 'not_found'
    assert any(value['literal'] == 'xsi:nil' for value in report.comparison_requests)
    assert report.status == 'mapping_valid'
