"""Generated cases share caller-controlled replay, clocks and seeds in isolated JVMs."""
import pytest
from models.executable_verification_settings import ExecutableVerificationSettings
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.verification_cases import controlled_cases
from tools.behavior_verification.boundary_verification import verify_boundary
from test_behavior_verification_boundaries import boundary_tool
from test_boundary_harness import controlled_unit
from types import SimpleNamespace


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


def test_generated_inputs_receive_identical_supplied_replay_and_runtime_controls(boundary_tool,tmp_path):
    unit,boundary,left,right,examples=controlled_unit(boundary_tool)
    settings=ExecutableVerificationSettings(mode='executable_boundary_v1',random_cases=0,seed=91,clock_millis=1234567890000,
        replays={unit['unit_id']:examples[0].external_responses})
    cases=controlled_cases(unit,boundary,SimpleNamespace(settings_bindings={}),[],executable_settings=settings)
    assert cases==controlled_cases(unit,boundary,SimpleNamespace(settings_bindings={}),[],executable_settings=settings)
    selected=[cases[0],next(c for c in cases if 'input' not in c.initial_context)]
    report=verify_boundary(unit,boundary,left,right,selected,tmp_path/'controlled-inputs',tool=boundary_tool,candidate_label='input_generator_fixture')
    assert report.status=='matched_observed_cases',report.model_dump_json(indent=2)
    assert all(case['legacy']['external_calls']==case['native']['external_calls'] for case in report.cases)
    assert all(case['legacy']['context']['balance']=='10' for case in report.cases)
    assert all(case['legacy']['context']['clock']=={'$date_millis':settings.clock_millis} for case in report.cases)
    assert not report.exhaustive_equivalence
