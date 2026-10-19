"""Compile operation code, plan original routes and accept one test scenario at a time."""

import json
from models.native_unit_bundle import NativeUnitBundle
from models.route_test_plan import RouteTestPlan
from agents.behavior_conversion.operation_route_tests import IMPLEMENTATION, PLAN, SCENARIO
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.compatibility import versioned_requirements
from runtime.behavior_conversion.route_test_plan import validate_route_plan, write_route_plan
from runtime.behavior_conversion.route_test_state import validate_child, stale_scenario_files, retire_removed_scenarios
from runtime.behavior_conversion.bundle_output import verify_manifest
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.behavior_units import snapshot, save


def generate_incremental_operation(conn, config, profile, identity, payload, validator,
                                   provisional_validator, scenario_validator, directory, model_call=None):
    """Return only a fully tested operation; individual successful phases are durable."""
    implementation_request = dict(payload, kind="service", assembly_phase="implementation_compile")
    implementation_request.pop("testing_contract", None)
    def validate_implementation(bundle, cached=False):
        if any(not file.path.startswith("src/main/java/") for file in bundle.files):
            raise ValueError("Provisional assembly must return main implementation files only; route tests follow separately")
        validate_child(conn, config, identity, "service_implementation:" + identity,
            bundle, cached, provisional_validator)
    implementation, implementation_hash = generate(conn, config, profile, "service_implementation", identity,
        IMPLEMENTATION, implementation_request, NativeUnitBundle, validate_implementation, model_call,
        "Operation implementation: " + identity, require_coverage=False)
    source_revision = stable_id(implementation_hash, [file.model_dump() for file in implementation.files], implementation.operation_contract.model_dump())
    platform = payload.get("testing_contract", {}).get("requirement", {}).get("requirement_id")
    requirements = {item["requirement_id"]: item["description"] for item in versioned_requirements(profile, "service", implementation_request)
        if item["requirement_id"] != platform}
    routing = payload["closure"].get("routing_graph", {})
    plan_request = dict(payload, kind="service", assembly_phase="route_test_plan", requirements=requirements,
        entry_step=next(iter(routing), None), assembled_code=[file.model_dump() for file in implementation.files],
        operation_contract=implementation.operation_contract.model_dump(), source_revision=source_revision)
    plan_request.pop("testing_contract", None)
    plan, plan_hash = generate(conn, config, profile, "route_test_plan", identity, PLAN, plan_request, RouteTestPlan,
        validator=lambda output, cached: validate_route_plan(output, routing, requirements), model_call=model_call,
        label="Route-test plan: " + identity)
    report = write_route_plan(directory, identity, plan)
    stale_files, removed = stale_scenario_files(conn, config, identity, plan, source_revision)
    pending_stale = set(stale_files)
    tests, coverage, test_hashes = [], {}, []
    dependencies = list(implementation.dependencies)
    for number, scenario in enumerate(plan.scenarios, 1):
        name = "Route" + stable_id(identity, scenario.scenario_id)[:12] + "Test"
        package = implementation.operation_contract.service_api.type_name.rsplit(".", 1)[0] + ".routing"
        test_path = "src/test/java/" + package.replace(".", "/") + "/" + name + ".java"
        scenario_identity = identity + ":" + scenario.scenario_id
        request = dict(payload, kind="service", assembly_phase="single_route_test",
            requirements={key: requirements[key] for key in scenario.covers},
            scenario=scenario.model_dump(), assembled_code=[file.model_dump() for file in implementation.files],
            operation_contract=implementation.operation_contract.model_dump(), source_revision=source_revision,
            expected_test_path=test_path, test_package=package, test_class=name)
        def validate_test(bundle, cached=False):
            if bundle.unresolved_questions:
                raise ValueError("Unresolved scenario evidence: " + "; ".join(bundle.unresolved_questions))
            if len(bundle.files) != 1 or bundle.files[0].path != test_path:
                raise ValueError("Scenario must return exactly its assigned test file: " + test_path)
            if bundle.operation_contract or bundle.unit_contract:
                raise ValueError("Scenario tests must not replace operation or unit contracts")
            # Coverage is an application-owned link to this validated scenario, not model metadata.
            bundle.coverage = {key: [test_path] for key in scenario.covers}
            validate_child(conn, config, identity, "route_scenario:" + scenario_identity, bundle, cached,
                scenario_validator(scenario_identity, scenario.covers, excluded_tests=tuple(pending_stale)))
        output, fingerprint = generate(conn, config, profile, "route_scenario_test", scenario_identity,
            SCENARIO, request, NativeUnitBundle, validate_test, model_call,
            f"Route scenario {number}/{len(plan.scenarios)}: {scenario.description} ({identity})", require_coverage=False)
        tests.extend(output.files)
        pending_stale.discard(test_path)
        dependencies.extend(output.dependencies)
        test_hashes.append(fingerprint)
        for key in scenario.covers:
            coverage.setdefault(key, []).append(test_path)
    merged = {}
    for dependency in dependencies:
        key = (dependency.group_id, dependency.artifact_id, dependency.version, dependency.scope)
        if key not in merged:
            merged[key] = dependency.model_copy(deep=True)
        else:
            merged[key].required_classes = sorted(set(merged[key].required_classes + dependency.required_classes))
    complete = implementation.model_copy(update={"files": [*implementation.files, *tests],
        "coverage": coverage, "dependencies": list(merged.values())})
    fingerprint = stable_id(implementation_hash, plan_hash, test_hashes, complete.model_dump())
    prior = snapshot(conn, config.run_id, "service", identity)
    manifest = json.loads(snapshot(conn, config.run_id, "manifest", "service_implementation:" + identity)["data_json"])
    verify_manifest(manifest["project"], {name: digest for name, digest in stale_files.items() if name not in {file.path for file in complete.files}})
    validator(complete, cached=bool(prior and prior["status"] == "accepted" and prior["fingerprint"] == fingerprint),
        excluded_tests=tuple(stale_files))
    retire_removed_scenarios(conn, config, removed)
    save(conn, config.run_id, "service", identity, fingerprint, complete.model_dump(mode="json"))
    save(conn, config.run_id, "route_test_report", identity, fingerprint,
        dict(plan_path=str(report), scenarios=[scenario.scenario_id for scenario in plan.scenarios], coverage=coverage))
    return complete, fingerprint
