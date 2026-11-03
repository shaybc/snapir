"""Retain XML test quality and automatic production repair after internal-call gates retire."""
from types import SimpleNamespace
import pytest
from runtime.component_conversion.format_chain_tests import validate_chain_tests,assertion_regression


def test_xml_oracles_and_value_regressions_route_different_responsibilities():
    payload={'format_chains':[{}]}
    for text in ('assertEquals("<Value/>", result);','assertTrue(result.contains("<Value/>"));'):
        with pytest.raises(ValueError,match='structurally|structure'):
            validate_chain_tests(SimpleNamespace(files=[SimpleNamespace(content=text)]),payload)
    validate_chain_tests(SimpleNamespace(files=[SimpleNamespace(content='assertEquals("", actual); assertEquals("Value", element.getNodeName());')]),payload)
    error=ValueError('expected empty, got null')
    error.test_correction={'diagnostics':[{'category':'assertion_failure','expected_value':'','actual_value':'null'}]}
    proof=assertion_regression(error,payload)
    assert proof['test_correction']['diagnostics'][0]['expected_value']==''
    assert 'do not weaken' in proof['errors'][0]
    error.test_correction['diagnostics'][0]['category']='test_error'
    assert assertion_regression(error,payload) is None
