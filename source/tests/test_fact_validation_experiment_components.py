"""Factless test requests preserve source entries, typed contracts and chain obligations."""
from copy import deepcopy
import pytest
from models.pipeline_configuration import PipelineConfiguration
from runtime.component_conversion.requests import build_component_request
from tools.conversion_tools.component_identity import component_group
from test_component_formats import format_case
from test_behavior_verification_boundaries import boundary_tool
from test_fact_validation_experiment import selected_jdk


def test_complete_format_without_facts_is_allowed_only_in_test_profile(format_case):
    _, _, normal, _, plan, boundaries, units = format_case
    missing = deepcopy(boundaries)
    for boundary in missing['boundaries'].values():
        boundary['parser_checklist'] = None
        boundary['basic_parser_checklist'] = None
    group = component_group(plan, plan.unit_roots['response'])
    with pytest.raises(ValueError, match='parser checklist'):
        build_component_request(plan, group, missing, [], normal, check_budget=False, units=units)
    data = normal.model_dump(mode='json')
    data.update(staged_unit_conversion=True, metadata_checklist_batching=True,
                executable_verification=dict(mode='conversion_checklist_v1', experimental_disable_facts=True))
    experimental = PipelineConfiguration.model_validate(data)
    request, _ = build_component_request(plan, group, missing, [], experimental, check_budget=False, units=units)
    assert request['parser_checklist'] == []
    assert request['source_entry_points']
    assert request['requirements']['configured-format-structure']
    assert request['conversion_acceptance_policy']['experimental_only']
    assert 'format_chain_policy' in request
    assert request['analysis_tool_hash'] == boundaries['analysis_tool_hash']
