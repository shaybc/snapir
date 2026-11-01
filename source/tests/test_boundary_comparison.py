"""Check strict result comparison independently from JVM adapters or generation."""
import pytest
from models.boundary_observation import BoundaryObservation
from tools.behavior_verification.boundary_comparison import compare_boundary_observations
from tools.behavior_verification.boundary_xml import xml_structure


def observation(**values):
    return BoundaryObservation(case_id='case', status='completed', **values)


def test_attribute_order_is_normalized_but_prefixes_are_not():
    a = '<r xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" a="1" xsi:nil="true"/>'
    b = '<r xsi:nil="true" a="1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></r>'
    c = b.replace('xsi', 'wtc')
    assert not compare_boundary_observations(observation(output=a), observation(output=b), xml_output=True)
    assert compare_boundary_observations(observation(output=a), observation(output=c), xml_output=True)
    assert xml_structure('<a b="2" c="3"/><d/>') == xml_structure('<a c="3" b="2"></a><d/>')
    assert not compare_boundary_observations(observation(output='fixed width'), observation(output='fixed width'), xml_output=True)
    assert compare_boundary_observations(observation(output='fixed width'), observation(output='fixed  width'), xml_output=True)[0]['reason'] == 'Observable value differs'


@pytest.mark.parametrize('a,b', [('<r/>','<r><a/></r>'), ('<r><a/></r>', '<r><a xsi:nil="true" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/></r>'),
    ('<r> a </r>','<r>a</r>'), ('<r><a/><b/></r>','<r><b/><a/></r>'), ('<r xmlns="one"/>','<r xmlns="two"/>')])
def test_significant_xml_differences_survive_normalization(a, b):
    assert compare_boundary_observations(observation(output=a), observation(output=b), xml_output=True)


def test_only_explicit_element_only_whitespace_is_ignored():
    a, b = '<r>\n <a/>\n</r>', '<r><a/></r>'
    assert xml_structure(a) != xml_structure(b)
    assert xml_structure(a, ('/r',)) == xml_structure(b, ('/r',))
    assert xml_structure('<r><a> </a></r>', ('/r',)) != xml_structure('<r><a/></r>', ('/r',))


def test_context_writes_removals_exceptions_and_external_order_are_observable():
    left = observation(context={'x': None}, writes=[{'key': 'x', 'value': None}], removals=[{'key': 'old', 'value': 2}],
        external_calls=[{'target': 'one', 'arguments': ['x']}, {'target': 'two', 'arguments': ['y']}], exception={'type': 'java.lang.IllegalArgumentException', 'message': 'original'})
    right = observation(context={}, external_calls=list(reversed(left.external_calls)), exception={'type': 'java.lang.IllegalStateException', 'message': 'different'})
    paths = {item['path'] for item in compare_boundary_observations(left, right)}
    assert {'context.x', 'writes.length', 'removals.length', 'exception.type', 'external_calls[0].target'} <= paths


def test_incomplete_execution_never_matches_and_numbers_are_not_strings():
    incomplete = BoundaryObservation(case_id='case', status='verification_incomplete')
    assert compare_boundary_observations(incomplete, incomplete)
    assert compare_boundary_observations(observation(output='1'), observation(output=1))
    assert compare_boundary_observations(observation(output={'$decimal': '1.0'}), observation(output=1))
    assert compare_boundary_observations(observation(output={'$decimal': '1.00'}), observation(output={'$decimal': '1.0'}))


def test_typed_case_protocol_preserves_dates_empty_null_and_control_characters():
    from tools.behavior_verification.boundary_protocol import value_element, read_value
    value = {'date': {'$date_millis': 12345}, 'decimal': {'$decimal': '1.25'}, 'empty': '', 'null': None, 'text': 'nul\0 and \ud800'}
    assert read_value(value_element(value)) == value
