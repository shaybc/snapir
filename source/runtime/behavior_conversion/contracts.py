"""Reconcile complete configured-unit evidence into explicit operation connection contracts."""

from pathlib import Path
from models.behavior_unit import SourceEvidence
from models.native_unit_bundle import NativeUnitBundle
from models.operation_data_contract import OperationDataContract
from runtime.behavior_conversion.generation import EvidenceSummary, bounded_unit_evidence, generate
from runtime.behavior_conversion.request_context import encode_request
from runtime.behavior_conversion.bundle_output import validate_bundle
from tools.component_inventory_tools.identity import stable_id
from agents.behavior_conversion.contract_extraction import INSTRUCTION
from constants import JAVA_PACKAGE_BASE


def prepare_contract(conn, config, profile, closure, units, model_call=None):
    """Read complete configured bundles and validate contracts for every expected unit."""
    units = list({unit.unit_id: unit for unit in units}.values())
    evidence = [bounded_unit_evidence(conn, config, profile, unit, model_call) for unit in units]
    sources = {source.identity: source for unit in units for source in unit.sources}
    operation_sources = []
    for item in closure.get("conversion_components", []):
        if item["kind"] == "ibm_java" and item["logical_id"] not in sources:
            source = SourceEvidence(identity=item["logical_id"],
                content=Path(item["source_file"]).read_text(encoding="utf-8-sig"), content_hash=item["source_hash"])
            sources[source.identity] = source
            operation_sources.append(source.model_dump(mode="json"))
    consumer = closure["channel"] + "/" + closure["operation_id"]
    contract_package = JAVA_PACKAGE_BASE + ".contracts.c" + stable_id(
        [(unit.fingerprint, unit.kind) for unit in units])[:12]
    request = dict(operation_id=closure["operation_id"], channel=closure["channel"],
        operation=closure, units=evidence,
        operation_sources=operation_sources, contract_package=contract_package,
        unit_package=JAVA_PACKAGE_BASE + ".units",
        unit_data_packages={unit.unit_id: JAVA_PACKAGE_BASE + ".contracts.u" + unit.fingerprint[:12] for unit in units},
        unit_api_packages={unit.unit_id: JAVA_PACKAGE_BASE + ".units.u" + unit.fingerprint[:12] for unit in units},
        java_version=profile.java_version)
    # Keep each configured unit and all its supporting sources together.
    request["operation"] = {key: value for key, value in closure.items() if key not in (
        "conversion_components", "composer_behavior_evidence")}
    try:
        encode_request(dict(request, schema=OperationDataContract.model_json_schema()), INSTRUCTION,
                       profile.behavior_context_chars)
    except ValueError:
        # Individual bundles can fit while their combined contract request cannot.
        compact = []
        for item in evidence:
            summary, _ = generate(conn, config, profile, "contract_evidence", item["unit_id"],
                "Extract the typed inputs, outputs, collaborators, transformations and outcomes needed to connect this complete configured unit. Read its XML and supporting classes together. Preserve evidence identities and unresolved behavior. Return schema JSON.",
                dict(unit=item), EvidenceSummary, model_call=model_call,
                label="Contract evidence bundle: " + item["logical_id"])
            compact.append(dict(unit_id=item["unit_id"], kind=item["kind"], logical_id=item["logical_id"],
                configuration_xml=item["configuration_xml"], referenced_definitions=item["referenced_definitions"],
                evidence_ids=[source.identity for unit in units if unit.unit_id == item["unit_id"] for source in unit.sources],
                findings=summary.model_dump(mode="json")))
        request["units"] = compact

    def validate(contract, cached=False):
        if contract.unresolved_questions:
            raise ValueError("Operation contract has unresolved behavior: " + "; ".join(contract.unresolved_questions))
        ids = [item.unit_id for item in contract.units]
        if set(ids) != {unit.unit_id for unit in units} or len(ids) != len(set(ids)):
            raise ValueError("Operation contract must cover every configured unit exactly once")
        from tools.component_inventory_tools.dependency_order import dependency_first_order
        dependencies = {}
        for item in contract.units:
            if not any(api.method_signatures for api in item.apis):
                raise ValueError("Each configured unit must expose its native conversion/business methods")
            if not set(item.dependency_units).issubset(set(ids)):
                raise ValueError("Contract references an unknown unit dependency")
            dependencies[item.unit_id] = item.dependency_units
            allowed = set(sources) | {unit.unit_id for unit in units}
            if not set(item.evidence_ids).issubset(allowed):
                raise ValueError("Contract cites unavailable source evidence")
        dependency_first_order(ids, dependencies)
        files = validate_bundle(NativeUnitBundle(files=contract.sources))
        for name in files:
            packages = [contract_package, *request["unit_data_packages"].values()]
            if not any(name.startswith("src/main/java/" + package.replace(".", "/") + "/") for package in packages):
                raise ValueError("Contract data/interface sources must use the assigned contract package")
        all_apis = [api.type_name for item in contract.units for api in item.apis]
        if len(all_apis) != len(set(all_apis)):
            raise ValueError("Configured units cannot own conflicting public APIs")
        if not contract.service_api.method_signatures:
            raise ValueError("The native operation must declare its business service methods")
        if any(not name.startswith(JAVA_PACKAGE_BASE + ".") for name in [*all_apis, contract.service_api.type_name]):
            raise ValueError("Planned implementation APIs must use the native package")
        by_id = {item.unit_id: item for item in contract.units}
        for role, field in (("csRequestFormat", "request_wire_type"), ("csReplyFormat", "success_wire_type"),
                            ("csErrorReplyFormat", "error_wire_type")):
            name = closure.get("ref_formats", {}).get(role)
            if name:
                matching = [unit for unit in units if unit.logical_id == name and unit.kind != "configured_step"]
                wire = getattr(contract, field)
                if not wire or not any(wire in {api.type_name for api in by_id[unit.unit_id].apis} for unit in matching):
                    raise ValueError("Format wire type must be declared in its owning unit API: " + role)
    return generate(conn, config, profile, "contract", consumer, INSTRUCTION, request,
                    OperationDataContract, validate, model_call, "Data contracts: " + consumer)
