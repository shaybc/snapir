from __future__ import annotations

from models.conversion_models import DbLookupRequirement, RoutingPlan
from models.validation_models import StubSpec


def generate_stub_spec(
    operation_id: str,
    db_lookups: list[DbLookupRequirement],
    routing_plan: RoutingPlan,
) -> StubSpec:
    """Generate deterministic backend stub scenarios for an operation."""
    scenarios = []
    for step in routing_plan.steps:
        for rc, target in step.transitions.items():
            if str(target) != "end":
                continue
            scenario = "success" if str(rc) == "0" else f"error_rc_{rc}"
            scenarios.append(
                {
                    "endpoint": f"/stub/{operation_id}/{step.step_id}/{rc}",
                    "method": "POST",
                    "request_pattern": step.step_id,
                    "response_body": f"<response><returnCode>{rc}</returnCode></response>",
                    "scenario": scenario,
                }
            )
    for lookup in db_lookups:
        scenarios.append(
            {
                "endpoint": f"/stub/{operation_id}/db/{lookup.field_name}",
                "method": "POST",
                "request_pattern": lookup.key_value_field,
                "response_body": f"<lookup><{lookup.field_name}>TEST_VALUE</{lookup.field_name}></lookup>",
                "scenario": f"db_lookup_{lookup.field_name}",
            }
        )
    return StubSpec(
        operation_id=operation_id,
        backend_endpoint=f"/stub/{operation_id}",
        scenarios=scenarios,
    )
