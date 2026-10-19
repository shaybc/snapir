"""Replay annotation detection and oversized stage-six corrections without altering accepted work."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from runtime.service_generation.bean_methods import bean_methods
from runtime.service_generation.correction_payload import deduplicate_generation_correction
from runtime.service_generation.operation_wiring import validate_operation_wiring, WIRING_INSTRUCTION
from runtime.service_generation.response import parse_service_response, RESPONSE_INSTRUCTION
from runtime.behavior_conversion.request_context import encode_request


def latest():
    return json.loads((Path(__file__).parent / 'fixtures/latest_annotated_bean_failure.json').read_text())


def test_latest_annotated_datasource_factory_is_recognized_without_relaxing_other_checks():
    fixture = latest()
    first, second = [parse_service_response(response) for response in fixture['responses']]
    with pytest.raises(ValueError, match='missing real bean factories.*javax.sql.DataSource'):
        validate_operation_wiring(first['files'], fixture['contract'])
    factories = list(bean_methods(second['files']['src/main/java/com/company/generated/config/AppConfig.java']))
    assert ('DataSource', 'dataSource', ['dataSource']) in factories
    # The response has a different startup-test form; that independent check still runs.
    with pytest.raises(ValueError, match='executable Spring wiring test'):
        validate_operation_wiring(second['files'], fixture['contract'])


def test_annotations_modifiers_aliases_and_nested_arguments_are_generic():
    source = '''class Config {
      // @Bean public Fake wrong() {}
      String text = "@Bean public Fake wrong() {}";
      @Deprecated @org.springframework.context.annotation.Bean(name={"primary", "alias"}, destroyMethod="close")
      @Other(value=@Nested(values={"(", ")"})) public static final example.Resource resource() { return null; }
      @Bean( value = "second" ) @Qualifier("notTheBeanName") protected example.Resource other() { return null; }
      @Bean(initMethod="initialize") @Any public java.util.List<String> list() { return null; }
    }'''
    assert list(bean_methods(source)) == [
        ('example.Resource', 'resource', ['primary', 'alias']),
        ('example.Resource', 'other', ['second']),
        ('java.util.List<String>', 'list', ['list'])]


def test_latest_correction_fits_without_losing_any_code_dependency_or_diagnostic():
    payload = latest()['correction_request']
    original = deepcopy(payload)
    instruction = WIRING_INSTRUCTION + RESPONSE_INSTRUCTION + 'x' * 2500
    with pytest.raises(ValueError, match='context budget'):
        encode_request(payload, instruction, 180000)
    compact = deduplicate_generation_correction(payload)
    request, encoded = encode_request(compact, instruction, 180000)
    assert len(encoded) + len(instruction) <= 180000
    assert request['previous_generation'] == payload['previous_generation']
    assert request['approved_sources'] == payload['approved_sources']
    assert request['operation'] == payload['operation']
    assert request['validation_feedback']['error'] == payload['validation_feedback']['error']
    assert request['validation_feedback']['generation_output_ref'] == 'previous_generation'
    assert 'generation_output' not in request['validation_feedback']
    assert payload == original


def test_different_project_versions_and_initial_requests_are_not_deduplicated():
    request = {'previous_generation': {'files': {'A.java': 'latest'}},
               'validation_feedback': {'generation_output': {'files': {'A.java': 'older'}}}}
    assert deduplicate_generation_correction(request) == request
    assert deduplicate_generation_correction({'approved_sources': {'A.java': 'source'}}) == {'approved_sources': {'A.java': 'source'}}
