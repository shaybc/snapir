"""Bindings wire values without implementing the format's business rules."""
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.format_comparison_plan import FormatComparisonEntry
from models.native_unit_bundle import NativeSourceFile
from runtime.format_comparison.bindings import resolved_binding
from test_format_context_discovery import channel_plan


def test_disabled_by_default_and_configuration_selectors_are_exact():
    assert not PipelineConfiguration().format_comparison.enabled
    sources = [NativeSourceFile(path='src/main/java/nativecode/F.java', content='package nativecode; public class F {}')]
    entry = FormatComparisonEntry(direction='format', binding=dict(owner_type='nativecode.F', method_name='format',
        constructor_arguments=[dict(type_name='java.lang.String', source='configuration', key='dataName')],
        arguments=[dict(type_name='java.lang.String', source='context', key='@configuration:dataName')]))
    binding = resolved_binding(entry, {'effective_configuration': {'attributes': {'dataName': 'Account.Flag'}}}, sources)
    assert binding.arguments[0].key == 'Account.Flag'
    assert entry.binding.arguments[0].key == '@configuration:dataName'


def test_diagnostic_setting_does_not_replace_or_weaken_conversion_policy():
    from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy
    profile = PipelineConfiguration(executable_verification={'mode': 'conversion_checklist_v1'})
    previous = conversion_policy(profile)
    profile.format_comparison.enabled = True
    assert profile.executable_verification.mode == 'conversion_checklist_v1'
    assert conversion_policy(profile) == previous


def test_unsafe_case_names_cannot_escape_disposable_workspace():
    from models.format_comparison_case import FormatComparisonCase
    with pytest.raises(ValueError, match='safe'):
        FormatComparisonCase(case_id='../outside', binding_id='write')


@pytest.mark.parametrize('change', [dict(method_name='format(input.trim())'), dict(owner_type='java.lang.System'),
    dict(configuration_setters={'setFlag': dict(type_name='java.lang.String', source='context', key='flag')})])
def test_expressions_external_owners_and_non_configuration_setters_rejected(change):
    plan = channel_plan(); entry = plan.entries['write'].model_copy(deep=True)
    entry.binding = entry.binding.model_copy(update=change)
    with pytest.raises((ValueError, AttributeError)):
        resolved_binding(entry, plan.original_unit, plan.native_sources)

