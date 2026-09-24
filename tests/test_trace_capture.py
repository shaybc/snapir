from __future__ import annotations

from models.conversion_models import RoutingPlan, RoutingStep
from tools.trace_capture_tools.trace_scenario_builder import derive_trace_scenarios


def test_derive_trace_scenarios_with_two_step_branch_plan_produces_multiple_scenarios():
    plan = RoutingPlan(
        operation_id="TransferFunds",
        channel="INTERNET",
        has_finally_step=False,
        steps=[
            RoutingStep(
                step_id="StepA",
                step_index=0,
                impl_class="StepA",
                transitions={"0": 1, "4": "end"},
            ),
            RoutingStep(
                step_id="StepB",
                step_index=1,
                impl_class="StepB",
                transitions={"0": "end"},
            ),
        ],
    )

    scenarios = derive_trace_scenarios(plan)

    assert len(scenarios) >= 2
    assert ["StepA", "StepB"] in [scenario.step_sequence for scenario in scenarios]
    assert ["StepA"] in [scenario.step_sequence for scenario in scenarios]


def test_on_return_path_produces_business_error_scenario():
    plan = RoutingPlan(
        operation_id="TransferFunds",
        channel="INTERNET",
        has_finally_step=False,
        steps=[
            RoutingStep(
                step_id="StepA",
                step_index=0,
                impl_class="StepA",
                transitions={"4": "end"},
                return_body_switches={"on4Return": "ErrorResponse"},
            ),
        ],
    )

    scenarios = derive_trace_scenarios(plan)

    assert scenarios[0].name == "business_error_StepA"


def test_identical_path_sequences_are_deduplicated():
    plan = RoutingPlan(
        operation_id="TransferFunds",
        channel="INTERNET",
        has_finally_step=False,
        steps=[
            RoutingStep(
                step_id="StepA",
                step_index=0,
                impl_class="StepA",
                transitions={"0": "end", "1": "end"},
            ),
        ],
    )

    scenarios = derive_trace_scenarios(plan)

    assert len(scenarios) == 1
    assert scenarios[0].step_sequence == ["StepA"]
