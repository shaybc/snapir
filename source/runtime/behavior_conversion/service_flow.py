"""Assemble ordinary native service methods against accepted behavior-unit contracts."""

from agents.behavior_conversion.service_flow import INSTRUCTION
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.generation import generate
from pathlib import Path


def service_request(profile, closure, contract, accepted_units):
    """Build the explicit workflow contract independently of its generation engine."""
    requirements = {"route-" + name: str(value) for name, value in closure.get("routing_graph", {}).items()}
    requirements["operation-flow"] = "Preserve the configured operation order, outcome/error branches and initialization"
    requirements.update(contract.service_requirements if contract else {})
    unit_sources = {identity for item in accepted_units.values() for identity in item.get("source_ids", [])}
    operation_sources = [dict(identity=item["logical_id"], content_hash=item["source_hash"],
        content=Path(item["source_file"]).read_text(encoding="utf-8-sig"))
        for item in closure.get("conversion_components", [])
        if item["kind"] == "ibm_java" and item["logical_id"] not in unit_sources]
    return dict(operation_id=closure["operation_id"], closure={key: value for key, value in closure.items()
        if key not in ("conversion_components", "composer_behavior_evidence")},
        contract=contract.model_dump(mode="json") if contract else None, accepted_units=accepted_units,
        operation_sources=operation_sources,
        requirements=requirements, java_version=profile.java_version)


def generate_service(conn, config, profile, closure, contract, accepted_units, validator, model_call=None):
    """Generate business workflow; deterministic generation remains a future option."""
    identity = closure["channel"] + "/" + closure["operation_id"]
    from runtime.behavior_conversion.dependency_context import known_dependencies
    project = Path(config.output_root) / closure["channel"] / closure["operation_id"]
    request = service_request(profile, closure, contract, accepted_units)
    request["known_dependencies"] = known_dependencies([project], [])
    from runtime.behavior_conversion.testing_contract import attach_testing_contract
    attach_testing_contract(request, profile)
    return generate(conn, config, profile, "service", identity, INSTRUCTION, request,
                    NativeUnitBundle, validator, model_call, "Operation flow: " + identity)
