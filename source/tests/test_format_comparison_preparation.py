"""Preparation proposes metadata only and remains separate from conversion acceptance."""
import json
from types import SimpleNamespace
from models.pipeline_configuration import PipelineConfiguration
from runtime.format_comparison.preparation import prepare_plan
from runtime.format_comparison.component_diagnostics import diagnose_component
from runtime.format_comparison.bindings import missing_binding_inputs
from test_format_context_discovery import channel_plan


def test_ai_discovery_and_binding_proposal_are_distinct_bounded_tasks(tmp_path):
    plan = channel_plan(); calls = []
    def model(instruction, request):
        calls.append(json.loads(request))
        if 'native_apis' in calls[-1]:
            return json.dumps(dict(entries={name: entry.model_dump(mode='json') for name, entry in plan.entries.items()}, unresolved=[]))
        plan.discovery.requirements[0].directions=['format']
        return plan.discovery.model_dump_json()
    profile = PipelineConfiguration(format_comparison={'enabled': True})
    result, report = prepare_plan(plan.label, plan.scope, plan.original_unit, plan.native_sources,
                                  plan.cases, profile, tmp_path, model_call=model)
    assert len(calls) == 2 and 'native_apis' in calls[0]
    assert calls[1]['execution']['selected_directions']==['format']
    assert result.entries['write'].binding.owner_type == 'nativecode.Format'
    assert result.discovery.requirements[0].context_key == 'runtime.channel'
    assert report['acceptance_changed'] is False


def test_unavailable_bindings_do_not_generate_adapter_java(tmp_path):
    plan = channel_plan()
    result, report = prepare_plan(plan.label, plan.scope, plan.original_unit, plan.native_sources, plan.cases,
                                  PipelineConfiguration(format_comparison={'enabled': True}), tmp_path)
    assert result is None and report['status'] == 'comparison_unavailable'
    assert not list(tmp_path.rglob('*.java'))


def test_missing_binding_input_is_not_implicitly_null():
    plan = channel_plan(); binding = plan.entries['write'].binding.model_copy(deep=True)
    from models.native_boundary_value import NativeBoundaryValue
    binding.arguments = [NativeBoundaryValue(type_name='java.lang.String', source='context', key='missing')]
    case = plan.cases[0]
    assert missing_binding_inputs(binding, case)
    assert not missing_binding_inputs(binding, case.model_copy(update={'intentionally_absent': ['missing']}))


def test_disabled_post_build_hook_does_not_touch_candidate_or_invoke_model(tmp_path):
    validator = SimpleNamespace(profile=PipelineConfiguration(), request={'configured_format': {'unit_id': 'unit'}})
    def forbidden(*args): raise AssertionError('No AI request permitted')
    assert diagnose_component(validator, None, {}, tmp_path / 'diagnostics', model_call=forbidden) is None
    assert not (tmp_path / 'diagnostics').exists()


def test_diagnostic_preparation_error_is_not_a_conversion_failure(tmp_path):
    validator = SimpleNamespace(profile=PipelineConfiguration(format_comparison={'enabled': True}),
                                request={'configured_format': {'unit_id': 'missing'}})
    result = diagnose_component(validator, None, {}, tmp_path)
    assert result['status'] == 'comparison_unavailable' and not result['acceptance_changed']
