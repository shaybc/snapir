"""Keep component examples distinct and reject unmapped tests before execution."""
import pytest
from agents.behavior_conversion.component_generation import component_instruction
from agents.behavior_conversion.format_component import format_instruction
from agents.behavior_conversion.native_instructions import native_instructions
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.bundle_output import validate_bundle


@pytest.mark.parametrize('factory', [component_instruction, format_instruction])
def test_component_prompt_has_no_unrelated_unit_example(factory):
    instruction = factory()
    assert '"coverage": {"business"' not in instruction
    assert '"unit_contract":' not in instruction
    assert 'coverage_response_example is a metadata template' in instruction
    assert 'exact requirements key' in instruction
    assert 'Write valid Java first, then encode it as JSON' in instruction


def test_other_native_requests_retain_the_existing_example():
    assert '"coverage": {"business"' in native_instructions('step')


def test_real_tests_require_exact_coverage_links_without_mutating_response():
    path = 'src/test/java/com/company/generated/SettingsTest.java'
    bundle = NativeUnitBundle(files=[dict(path=path, content='package com.company.generated; public class SettingsTest {}')],
                              coverage={'business': [path]})
    original = bundle.model_dump_json()
    with pytest.raises(ValueError) as rejected:
        validate_bundle(bundle, requirements={'entry-applications': 'Test applications', 'entry-channels': 'Test channels'})
    message = str(rejected.value)
    assert 'tests have not been run' in message
    assert 'entry-applications' in message and 'entry-channels' in message
    assert 'returned_coverage_keys' in message and 'available_test_paths' in message
    assert bundle.model_dump_json() == original
    bundle.coverage = {key: [path] for key in ['entry-applications', 'entry-channels']}
    assert path in validate_bundle(bundle, requirements=bundle.coverage)
    # Passing metadata validation alone does not run or accept these placeholder sources.
    bundle.coverage['entry-channels'] = ['src/test/java/com/company/generated/MissingTest.java']
    with pytest.raises(ValueError, match='entry-channels'):
        validate_bundle(bundle, requirements=bundle.coverage)
