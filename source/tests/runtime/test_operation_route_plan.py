"""Validate original edge coverage and render the exact route-test plan."""

import json
from pathlib import Path
import pytest
from models.route_test_plan import RouteTestPlan
from runtime.behavior_conversion.route_test_plan import validate_route_plan, write_route_plan


def saved_failure():
    return json.loads((Path(__file__).parent / "fixtures/operation_assembly_coverage_failures.json").read_text(encoding="utf-8"))[-1]


def plan_for(routing, requirements):
    scenarios = []
    def walk(source, path):
        for outcome, target in routing[source].items():
            edges = [*path, dict(source=source, outcome=outcome, target=target)]
            if target in routing:
                walk(target, edges)
            else:
                covers = ["route-" + edge["source"] for edge in edges if "route-" + edge["source"] in requirements]
                scenarios.append(dict(scenario_id="case" + str(len(scenarios) + 1),
                    description="Exercise original path " + str(len(scenarios) + 1), inputs=["Use inputs selecting the specified outcomes"],
                    dependency_setup=[str(edges)], expected_outcome="Preserve the evidenced terminal result and side effects",
                    covers=list(dict.fromkeys([*covers, "operation-flow"])), routes=edges))
    if routing:
        walk(next(iter(routing)), [])
    return RouteTestPlan(scenarios=scenarios)


def test_latest_failure_requires_all_original_branches_not_only_generated_routes(tmp_path):
    saved = saved_failure()
    assert saved["response"]["coverage"] == {}
    plan = plan_for(saved["routing_graph"], saved["requirements"])
    validate_route_plan(plan, saved["routing_graph"], saved["requirements"])
    assert any(edge.outcome == "onTimeoutDo" for case in plan.scenarios for edge in case.routes)
    report = write_route_plan(tmp_path, "INTERNET/TransferFundsOp", plan)
    assert report.is_file() and report.with_suffix(".json").is_file()
    assert "FraudCheck" in report.read_text(encoding="utf-8")
    assert RouteTestPlan.model_validate_json(report.with_suffix(".json").read_text()) == plan


@pytest.mark.parametrize("change", ["missing_branch", "invented_edge", "missing_requirement", "unknown_requirement", "duplicate_id", "disconnected_path", "unsupported_claim", "unknown_behavior"])
def test_invalid_plans_cannot_claim_complete_coverage(change):
    saved = saved_failure()
    plan = plan_for(saved["routing_graph"], saved["requirements"])
    if change == "missing_branch":
        plan.scenarios = [case for case in plan.scenarios if not any(edge.outcome == "onTimeoutDo" for edge in case.routes)]
    elif change == "invented_edge":
        plan.scenarios[0].routes[0].target = "InventedTarget"
    elif change == "missing_requirement":
        for case in plan.scenarios:
            case.covers = [name for name in case.covers if name != "operation-flow"]
    elif change == "unknown_requirement":
        plan.scenarios[0].covers.append("invented")
    elif change == "duplicate_id":
        plan.scenarios[1].scenario_id = plan.scenarios[0].scenario_id
    elif change == "disconnected_path":
        plan.scenarios[0].routes = plan.scenarios[0].routes[1:]
    elif change == "unsupported_claim":
        plan.scenarios[0].covers.append("route-ValidationFailed")
    else:
        plan.unresolved_questions = ["No evidence for a required route"]
    with pytest.raises(ValueError):
        validate_route_plan(plan, saved["routing_graph"], saved["requirements"])


def test_shortened_outcome_feedback_identifies_exact_original_edge():
    routing = {"Fetch": {"on0Do": "end", "onOtherDo": "end"}}
    requirements = {"route-Fetch": "Preserve Fetch routing", "operation-flow": "Preserve operation flow"}
    plan = plan_for(routing, requirements)
    plan.scenarios[0].routes[0].outcome = "0"
    with pytest.raises(ValueError) as failure:
        validate_route_plan(plan, routing, requirements)
    assert "('Fetch', '0', 'end')" in str(failure.value)
    assert "('Fetch', 'on0Do', 'end')" in str(failure.value)
    assert "('Fetch', 'onOtherDo', 'end')" in str(failure.value)
    assert "do not shorten outcome keys" in str(failure.value)
