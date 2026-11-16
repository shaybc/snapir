"""Select the supported full-conversion workflow without exposing implementation switches."""
from copy import deepcopy


FIXED_SETTINGS = dict(conversion_strategy='behavior_units', scoped_native_mode='component_first_v1',
    mapper_analysis_format='indexed-v1', mapper_vault_layout='scoped', target_languages=['java'],
    staged_unit_conversion=True, metadata_checklist_batching=True, cross_run_component_reuse=True,
    side_road_conversion=False, behavior_triage_enabled=True, model_provider='litellm',
    test_preparation=dict(mode='ai_shared_fixtures_v1'),
    executable_verification=dict(mode='test_based_v1', experimental_disable_facts=False),
    format_comparison=dict(enabled=True, collect_facts=False),
    unit_mutation_testing=dict(enabled=True), microservice=dict(enabled=True, require_helm_validation=True))


def completed_settings(values):
    """Return explicit immutable-policy choices merged with user inputs, without I/O."""
    result = {**values, **deepcopy(FIXED_SETTINGS)}
    if values.get('microservice', {}).get('helm_executable'):
        result['microservice']['helm_executable'] = values['microservice']['helm_executable']
    return result
