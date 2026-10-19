"""Orchestrate complete-format and configured-step conversion with durable gates."""

import json
import hashlib
from pathlib import Path
from models.migration_models import MigrationPlan
from models.native_unit_bundle import NativeUnitBundle
from runtime.human_gates import evaluate_gate
from runtime.workspace_paths import write_run_report, run_report_path
from tools.state_store_tools.runs import update_run_status
from tools.state_store_tools.behavior_units import initialize, save, snapshot
from tools.component_inventory_tools.identity import stable_id
from tools.component_inventory_tools.behavior_unit_usage import plan_unit_ownership
from tools.conversion_tools.behavior_unit_builder import build_behavior_units
from runtime.behavior_conversion.generation import generate, bounded_unit_evidence
from runtime.behavior_conversion.resume_budget import with_resume_budget
from runtime.behavior_conversion.dependency_context import known_dependencies
from runtime.behavior_conversion.testing_contract import attach_testing_contract, testing_contract
from runtime.behavior_conversion.bundle_output import validate_bundle, accept_bundle, verify_manifest, file_manifest
from runtime.behavior_conversion.validation_progress import progress_step
from runtime.behavior_conversion.ownership import project_for, create_native_context, library_dependency, consumer_artifact
from runtime.behavior_conversion.review import review_behavior
from runtime.behavior_conversion.revisions import generate_reviewed_bundle
from runtime.behavior_conversion.corrections import correction_feedback
from runtime.behavior_conversion.api_surface import api_surface


def _gate(conn, config, profile, directory, number, report, passed, phase):
    """Persist a report and bind the existing human gate to complete content."""
    write_run_report(directory, f"gate_{number}_report.txt", report)
    decision = evaluate_gate(conn, config.run_id, number, report, profile.gate_policies[str(number)], passed)
    if decision != "approved":
        update_run_status(conn, config.run_id, "paused" if decision == "pending" else "blocked", f"gate_{number}_{decision}")
        return False
    update_run_status(conn, config.run_id, "in_progress", phase)
    return True


def _bundle_validator(conn, config, profile, project, identity, apis, requirements, evidence, factory,
                      dependencies=(), require_tests=True, excluded_test_files=(), remove_excluded_tests=False):
    """Build/publish a candidate and verify accepted files during cached reuse."""
    def validate(bundle, cached=False):
        with progress_step("Validating Java files, method contracts, dependencies and behavior coverage"):
            files = validate_bundle(bundle, apis, requirements, evidence, profile.allowed_ibm_classes)
        previous = snapshot(conn, config.run_id, "manifest", identity)
        build_manifest = snapshot(conn, config.run_id, "project", str(project))
        if build_manifest:
            verify_manifest(project, json.loads(build_manifest["data_json"])["files"])
        if cached:
            if previous is None:
                raise ValueError("Accepted bundle manifest is missing")
            data = json.loads(previous["data_json"])
            expected = {name: hashlib.sha256(content.encode("utf-8")).hexdigest() for name, content in files.items()}
            if data["files"] != expected:
                raise ValueError("Accepted manifest does not match the requested native bundle")
            verify_manifest(project, data["files"])
            return
        owned = json.loads(previous["data_json"])["files"] if previous else {}
        if owned:
            verify_manifest(project, owned)
        validation, manifest = accept_bundle(project, files, factory, profile,
                                             [*dependencies, *bundle.dependencies], require_tests=require_tests,
                                             owned_files=owned,
                                             required_tests={name for requirement in requirements for name in bundle.coverage[requirement]},
                                             testing_contract=testing_contract(profile) if require_tests else None,
                                             excluded_test_files=excluded_test_files, remove_excluded_tests=remove_excluded_tests)
        save(conn, config.run_id, "manifest", identity, stable_id(manifest),
             dict(project=str(project), files=manifest, validation=validation))
        pom = file_manifest(project, ["pom.xml"])
        save(conn, config.run_id, "project", str(project), stable_id(pom), dict(files=pom))
    return validate


def _install(project, factory, profile):
    """Publish a verified native dependency before compiling its consumers."""
    context = factory(profile, project, Path(project).name)
    result = context.verifier.compile_project(project, context.allowed_ibm_artifacts, goal="install")
    if result.returncode:
        raise ValueError("Native library installation failed: " + (result.stdout or "") + "\n" + (result.stderr or ""))


def _dependency_validation_version(conn, run_id, category, identity, payload,
                                   key="dependency_validation", version="resolved-class-ownership-v1"):
    """Refresh failed validation requests without invalidating accepted units."""
    prior = snapshot(conn, run_id, category, identity)
    request = conn.execute("SELECT request_json FROM behavior_attempts WHERE run_id=? AND category=? AND identity=? ORDER BY rowid DESC LIMIT 1",
                           (run_id, category, identity)).fetchone()
    already_versioned = request and json.loads(request[0]).get(key)
    if not prior or prior["status"] != "accepted" or already_versioned:
        payload[key] = version


@with_resume_budget
def resume_behavior_pipeline(conn, config, profile, directory, *, model_call=None, context_factory=None, execution_plan=None):
    """Run the opt-in strategy without converting original classes one by one."""
    from runtime.managed_projects import create_build_context
    from runtime.planning import prepare_plan
    from agents.migration_planning.agent import get_operations_for_planning
    from agents.migration_planning.plan_validator import validate_migration_plan
    from runtime.gate_one_reports import write_gate_one_reports, read_gate_one_reports
    from tools.conversion_tools.closure_builder_tool import build_operation_closure
    from tools.conversion_tools.context_field_resolver_tool import resolve_context_fields
    from tools.source_discovery_tools.classpath import discover_java_classpath
    from tools.state_store_tools._json import loads
    initialize(conn)
    directory = Path(directory)
    factory = context_factory or create_build_context
    native_factory = lambda settings, project, artifact: create_native_context(config, settings, project, factory)
    operations = get_operations_for_planning(conn, config.run_id)
    row = conn.execute("SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1", (config.run_id,)).fetchone()
    if execution_plan is not None:
        plan = execution_plan
        selected = {(packet.channel, packet.operation_id) for batch in plan.batches for packet in batch.task_packets}
        if len(selected) != 1 or plan.run_id != config.run_id:
            raise ValueError('Sequential workflow requires one operation from the same run')
        operations = [item for item in operations if (item['channel'], item['operation_id']) in selected]
    elif row:
        plan = MigrationPlan.model_validate_json(row[0])
    else:
        update_run_status(conn, config.run_id, "in_progress", "planning")
        try:
            plan = prepare_plan(conn, config, profile, operations)
        except Exception:
            update_run_status(conn, config.run_id, "failed", "planning_failed")
            raise
    errors = validate_migration_plan(plan, config, conn) if execution_plan is None else []
    if errors:
        raise ValueError("Invalid saved migration plan: " + "; ".join(errors))
    classpath = discover_java_classpath(config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables)
    closures, by_operation, all_units, bindings = [], {}, {}, {}
    for batch in plan.batches:
        for packet in batch.task_packets:
            source = conn.execute("SELECT metadata_json FROM source_artifacts WHERE run_id=? AND kind='operation' AND logical_id=?",
                                  (config.run_id, packet.operation_id)).fetchone()
            context = loads(source[0], {}).get("operation_context") if source else None
            if context:
                resolve_context_fields(conn, context, packet.channel, config.run_id, config.source_root)
            closure = build_operation_closure(conn, packet.operation_id, packet.channel, config.run_id,
                config.source_root, config.vault_root, classpath_index=classpath, profile=profile).model_dump(mode="json")
            closures.append(closure)
            if closure["status"] != "READY":
                continue
            units, links = build_behavior_units(conn, config, closure, profile)
            consumer = packet.channel + "/" + packet.operation_id
            by_operation[consumer] = units
            bindings[consumer] = links
            for unit in units:
                if unit.unit_id in all_units:
                    all_units[unit.unit_id].consumers = sorted(set(all_units[unit.unit_id].consumers + unit.consumers))
                else:
                    all_units[unit.unit_id] = unit
    write_run_report(directory, "dependency_closure.json", json.dumps(closures, indent=2))
    preliminary = plan_unit_ownership(list(all_units.values()), profile)
    write_gate_one_reports(directory, conn, config, profile, plan, operations, None)
    library_report = directory / "reports/2_migration_planning/gate_1/shared_libraries.md"
    library_report.write_text("# Option two: preliminary complete-unit ownership\n\n" + json.dumps(
        dict(strategy=profile.conversion_strategy, units=[unit.model_dump(mode="json", exclude={"sources"}) for unit in all_units.values()],
             ownership=preliminary.model_dump(mode="json"), closure_ready=all(item["status"] == "READY" for item in closures)), indent=2), encoding="utf-8")
    report = read_gate_one_reports(directory)
    decision = evaluate_gate(conn, config.run_id, 1, report, profile.gate_policies["1"], True)
    if decision != "approved":
        update_run_status(conn, config.run_id, "paused" if decision == "pending" else "blocked", "gate_1_" + decision)
        return directory
    if any(item["status"] != "READY" for item in closures):
        update_run_status(conn, config.run_id, "blocked", "closures_blocked")
        return directory
    from runtime.behavior_conversion.operation_calls import order_closures
    try:
        closures = order_closures(conn, config, closures)
    except ValueError as exc:
        for item in closures:
            if item.get('operation_calls'):
                item['status'] = 'BLOCKED_UNRESOLVED_REFERENCE'
                item.setdefault('blocking_issues', []).append(dict(kind='BLOCKED_UNRESOLVED_REFERENCE',
                    entity_id=item['operation_id'], detail=str(exc)))
        write_run_report(directory, 'dependency_closure.json', json.dumps(closures, indent=2))
        update_run_status(conn, config.run_id, 'blocked', 'closures_blocked')
        return directory
    from runtime.service_connection_questions import resolve_pending_connections
    if not resolve_pending_connections(conn, config, profile, directory, all_units, native_factory):
        return directory
    update_run_status(conn, config.run_id, "in_progress", "conversion_pending")
    try:
        _convert_and_review(conn, config, profile, directory, closures, by_operation, all_units, bindings,
                            native_factory, model_call, execution_plan=execution_plan)
    except Exception:
        phase = conn.execute("SELECT current_phase FROM runs WHERE run_id=?", (config.run_id,)).fetchone()[0]
        update_run_status(conn, config.run_id, "failed", phase)
        raise
    return directory


def _convert_and_review(conn, config, profile, directory, closures, by_operation, all_units, bindings, factory, model_call, *, execution_plan=None):
    """Convert separate units, reuse accepted APIs, then assemble the operation."""
    from agents.behavior_conversion.format_mapping import INSTRUCTION as FORMAT
    from agents.behavior_conversion.configured_step import INSTRUCTION as STEP
    consumers = {item["channel"] + "/" + item["operation_id"] for item in closures}
    contracts = {}
    ownership = plan_unit_ownership(list(all_units.values()), profile)
    save(conn, config.run_id, "ownership", "native", ownership.fingerprint, ownership.model_dump(mode="json"))
    write_run_report(directory, "native_unit_plan.json", ownership.model_dump_json(indent=2))
    accepted, reports, installed = {}, [], set()
    ordered = sorted(all_units.values(), key=lambda unit: (
        unit.kind != "request_unformat", not bool(ownership.assignments[unit.unit_id]),
        unit.kind == "response_format", unit.unit_id))
    if any(item.get('operation_calls') for item in closures):
        operation_order = {item['channel'] + '/' + item['operation_id']: i for i, item in enumerate(closures)}
        ordered.sort(key=lambda unit: min(operation_order[name] for name in unit.consumers if name in operation_order))
    for position, unit in enumerate(ordered, 1):
        selected_consumers = [name for name in unit.consumers if name in consumers]
        targets = selected_consumers[:1] if ownership.assignments[unit.unit_id] else selected_consumers
        projects, builds = {}, {}
        reusable = {key: value for key, value in accepted.items()
                    if set(unit.consumers).issubset(all_units[key].consumers)}
        dependency_apis = [dict(unit_id=key, planned_apis=value["apis"],
                               verified_api_surface=value["public_api"],
                               input_type=value.get("input_type"), output_type=value.get("output_type"),
                               wire_type=value.get("wire_type")) for key, value in reusable.items()]
        for consumer in targets:
            project = project_for(config, unit.model_copy(update={"consumers": [consumer]}), ownership.assignments)
            projects[consumer] = project
            dependencies = []
            for key in reusable:
                target = consumer_artifact(accepted[key], consumer)
                if target["project"] != str(project):
                    other = Path(target["project"])
                    if str(other) not in installed:
                        _install(other, factory, profile)
                        installed.add(str(other))
                    dependencies.append(library_dependency(config, other))
            builds[consumer] = dependencies
        primary = targets[0]
        project, dependencies = projects[primary], builds[primary]
        payload = bounded_unit_evidence(conn, config, profile, unit, model_call)
        requirements = {"business": "Preserve this complete configured unit's evidenced behavior"}
        evidence_ids = [unit.unit_id, *(source.identity for source in unit.sources)]
        payload.update(requirements=requirements, evidence_ids=evidence_ids,
            converted_dependency_apis=dependency_apis, java_version=profile.java_version,
            native_package="com.company.generated.units.u" + unit.fingerprint[:12],
            artifact_owner=ownership.assignments[unit.unit_id], artifact_targets={name: str(root) for name, root in projects.items()},
            managed_dependencies=[item.model_dump(mode="json") for item in dependencies])
        if execution_plan is not None and ownership.assignments[unit.unit_id]:
            # A shared artifact keeps the same request identity as the wrapper advances consumers.
            payload['artifact_targets'] = {ownership.assignments[unit.unit_id]: str(project)}
        payload["known_dependencies"] = known_dependencies(projects.values(),
            [item for values in builds.values() for item in values])
        if unit.service_connections:
            from runtime.behavior_conversion.connection_contract import attach_connections
            attach_connections(payload, unit.service_connections)
        attach_testing_contract(payload, profile)
        payload["final_validation_feedback"] = correction_feedback(conn, config.run_id, "unit", unit.unit_id)
        payload["method_contract_validation"] = "resolved-java-types-v1"
        _dependency_validation_version(conn, config.run_id, "unit", unit.unit_id, payload,
                                       "generic_method_validation", "erased-type-arguments-v1")
        _dependency_validation_version(conn, config.run_id, "unit", unit.unit_id, payload)
        _dependency_validation_version(conn, config.run_id, "unit", unit.unit_id, payload,
                                       "transitive_class_validation", "resolved-transitive-api-v1")
        _dependency_validation_version(conn, config.run_id, "unit", unit.unit_id, payload,
                                       "source_comment_validation", "comments-ignored-v1")
        validators = [_bundle_validator(conn, config, profile, root,
            unit.unit_id if name == primary else unit.unit_id + ":local:" + name, (),
            requirements, evidence_ids, factory, builds[name]) for name, root in projects.items()]
        def validator(bundle, cached=False):
            if unit.operation_calls:
                from runtime.behavior_conversion.operation_calls import validate_operation_clients, verify_operation_contracts
                verify_operation_contracts(conn, config, unit.operation_calls)
                validate_operation_clients(bundle, unit.operation_calls)
            if unit.service_connections:
                from runtime.behavior_conversion.service_connection_freshness import verify_connection_sources
                verify_connection_sources(config, profile, unit.service_connections)
            api = bundle.unit_contract
            if api is None or api.unit_id != unit.unit_id:
                raise ValueError("Unit response must declare its own native interface contract")
            if not any(item.method_signatures for item in api.apis):
                raise ValueError("Unit must expose native conversion/business methods")
            if not set(api.dependency_units).issubset(reusable):
                raise ValueError("Unit references an interface that has not been accepted")
            validate_bundle(bundle, api.apis, requirements, evidence_ids, profile.allowed_ibm_classes)
            for validate in validators:
                validate(bundle, cached=cached)
        output, fingerprint, reviewed, review_hash = generate_reviewed_bundle(conn, config, profile, "unit", unit.unit_id,
            STEP if unit.kind == "configured_step" else FORMAT, payload, validator,
            lambda bundle: dict(unit=payload, generated_bundle=bundle.model_dump(mode="json"),
                validation=json.loads(snapshot(conn, config.run_id, "manifest", unit.unit_id)["data_json"])["validation"]),
            model_call, f"Unit {position}/{len(ordered)}: {unit.logical_id}")
        api = output.unit_contract
        manifest = json.loads(snapshot(conn, config.run_id, "manifest", unit.unit_id)["data_json"])
        accepted[unit.unit_id] = dict(unit_id=unit.unit_id, project=str(project), apis=[item.model_dump() for item in api.apis],
                                     fingerprint=fingerprint, files=manifest["files"], public_api=api_surface(output),
                                     contract=api.model_dump(mode="json"), input_type=output.input_type,
                                     output_type=output.output_type, wire_type=output.wire_type,
                                     source_ids=[source.identity for source in unit.sources])
        if not ownership.assignments[unit.unit_id]:
            accepted[unit.unit_id]["local_instances"] = {name: dict(unit_id=unit.unit_id, project=str(root),
                apis=[item.model_dump() for item in api.apis], fingerprint=fingerprint,
                public_api=accepted[unit.unit_id]["public_api"], contract=api.model_dump(mode="json"),
                input_type=output.input_type, output_type=output.output_type, wire_type=output.wire_type,
                source_ids=accepted[unit.unit_id]["source_ids"],
                files=json.loads(snapshot(conn, config.run_id, "manifest",
                    unit.unit_id if name == primary else unit.unit_id + ":local:" + name)["data_json"])["files"])
                for name, root in projects.items()}
        reports.append(dict(unit_id=unit.unit_id, logical_id=unit.logical_id, kind=unit.kind, project=str(project), consumers=unit.consumers, fingerprint=fingerprint,
            review_fingerprint=review_hash, review=reviewed.model_dump(), files=manifest["files"],
            local_instances=accepted[unit.unit_id].get("local_instances", {}),
            dependencies=[item.model_dump(mode="json") for item in [*dependencies, *output.dependencies]]))
        write_run_report(directory, "native_bundle_results.json", json.dumps(reports, indent=2))
    gate2 = json.dumps(dict(strategy="behavior_units", accepted_interfaces={key: value["contract"] for key, value in accepted.items()},
        ownership=ownership.model_dump(), units=reports), sort_keys=True)
    if not _gate(conn, config, profile, directory, 2, gate2,
        all(item["review"]["approved"] and not item["review"]["issues"] and not item["review"]["unresolved_questions"] for item in reports), "assembly_pending"):
        return
    operation_reports = []
    for closure in closures:
        consumer = closure["channel"] + "/" + closure["operation_id"]
        project = Path(config.output_root) / closure["channel"] / closure["operation_id"]
        sources = {key: consumer_artifact(accepted[value], consumer) for key, value in bindings[consumer].items()}
        dependencies = []
        for name in sorted({item["project"] for item in sources.values()} - {str(project)}):
            _install(Path(name), factory, profile)
            dependencies.append(library_dependency(config, Path(name)))
        requirements = {"route-" + key: str(value) for key, value in closure.get("routing_graph", {}).items()}
        requirements["operation-flow"] = "Preserve operation flow"
        build_validator = _bundle_validator(conn, config, profile, project, "service:" + consumer,
            (), requirements, (), factory, dependencies)
        provisional_build_validator = _bundle_validator(conn, config, profile, project, "service_implementation:" + consumer,
            (), (), (), factory, dependencies, require_tests=False)
        def validator(bundle, cached=False, provisional=False, excluded_tests=()):
            from runtime.behavior_conversion.operation_dependencies import validate_step_injection
            from runtime.behavior_conversion.operation_resources import validate_runtime_resources
            try:
                validate_step_injection(bundle, step_dependencies)
                validate_runtime_resources(bundle, runtime_resources)
            except ValueError as exc:
                raise ValueError("Operation constructor/resource contract: " + str(exc)) from exc
            protected = {name for unit in sources.values() for name in unit.get("files", {})}
            copied = {file.path for file in bundle.files}.intersection(protected)
            if copied:
                raise ValueError("Assembly must reuse accepted units, not return or overwrite their files: " + ", ".join(sorted(copied)))
            contract = bundle.operation_contract
            if contract is None:
                raise ValueError("Assembly must return its service and wire mapping metadata with its Java code")
            expected = {value for value in bindings[consumer].values()}
            if {item.unit_id for item in contract.units} != expected:
                raise ValueError("Assembly metadata must cover the accepted units")
            for item in contract.units:
                if item.model_dump(mode="json") != accepted[item.unit_id]["contract"]:
                    raise ValueError("Assembly changed an accepted interface")
            validate_bundle(bundle, [contract.service_api], () if provisional else requirements, (), profile.allowed_ibm_classes)
            build = provisional_build_validator if provisional else (
                _bundle_validator(conn, config, profile, project, "service:" + consumer,
                    (), requirements, (), factory, dependencies, excluded_test_files=excluded_tests,
                    remove_excluded_tests=True) if excluded_tests else build_validator)
            build(bundle, cached=cached)
        from runtime.behavior_conversion.service_flow import service_request
        from agents.behavior_conversion.service_flow import INSTRUCTION
        payload = service_request(profile, closure, None, sources)
        if closure.get('operation_calls'):
            from runtime.behavior_conversion.operation_calls import attach_operation_calls
            attach_operation_calls(conn, config, payload, closure['operation_calls'])
        from runtime.behavior_conversion.operation_dependencies import required_steps
        step_dependencies = required_steps(bindings[consumer], all_units, accepted)
        from runtime.behavior_conversion.operation_resources import required_resources
        runtime_resources = required_resources(step_dependencies, accepted,
            {key: unit.service_connections for key, unit in all_units.items()})
        payload["required_step_dependencies"] = step_dependencies
        payload["required_runtime_resources"] = runtime_resources
        connections = [connection for unit in by_operation[consumer] for connection in unit.service_connections]
        if connections:
            from runtime.behavior_conversion.connection_contract import attach_connections
            attach_connections(payload, connections)
        payload["constructor_example"] = (Path(__file__).resolve().parents[2] / "templates/native_operations/constructor_example.java").read_text(encoding="utf-8")
        payload["known_dependencies"] = known_dependencies([project], dependencies)
        attach_testing_contract(payload, profile)
        payload["final_validation_feedback"] = correction_feedback(conn, config.run_id, "service", consumer)
        payload["method_contract_validation"] = "resolved-java-types-v1"
        _dependency_validation_version(conn, config.run_id, "service", consumer, payload,
                                       "generic_method_validation", "erased-type-arguments-v1")
        _dependency_validation_version(conn, config.run_id, "service", consumer, payload)
        _dependency_validation_version(conn, config.run_id, "service", consumer, payload,
                                       "transitive_class_validation", "resolved-transitive-api-v1")
        _dependency_validation_version(conn, config.run_id, "service", consumer, payload,
                                       "source_comment_validation", "comments-ignored-v1")
        from runtime.behavior_conversion.compatibility import versioned_requirements
        platform_requirement = payload.get("testing_contract", {}).get("requirement", {}).get("requirement_id")
        requirements.update({item["requirement_id"]: item["description"] for item in
            versioned_requirements(profile, "service", dict(payload, kind="service"))
            if item["requirement_id"] != platform_requirement})
        from runtime.behavior_conversion.incremental_operation import generate_incremental_operation
        def incremental(request):
            return generate_incremental_operation(conn, config, profile, consumer, request, validator,
                lambda bundle, cached=False: validator(bundle, cached=cached, provisional=True),
                lambda identity, covers, excluded_tests=(): _bundle_validator(conn, config, profile, project,
                    "route_scenario:" + identity, (), covers, (), factory, dependencies, excluded_test_files=excluded_tests),
                directory, model_call)
        bundle, fingerprint, review, review_hash = generate_reviewed_bundle(conn, config, profile, "service", consumer,
            INSTRUCTION, payload, validator, lambda bundle: dict(closure=payload["closure"],
                accepted_units=sources, bundle=bundle.model_dump()),
            model_call, "Operation flow: " + consumer, bundle_generator=incremental)
        manifest = json.loads(snapshot(conn, config.run_id, "manifest", "service:" + consumer)["data_json"])
        contracts[consumer] = bundle.operation_contract
        api = bundle.operation_contract.service_api
        record = dict(operation_id=closure["operation_id"], channel=closure["channel"], project=str(project),
            fingerprint=fingerprint, service_api=api.model_dump(), contract=contracts[consumer].model_dump(),
            bindings=sources, files=manifest["files"], closure=closure, review=review.model_dump(),
            contract_project=str(project), contract_files=manifest["files"])
        if connections:
            record["service_connections"] = payload["service_connections"]
        save(conn, config.run_id, "operation", consumer, fingerprint, record)
        from tools.state_store_tools.operation_calls import load_graph
        graph = load_graph(conn, config.run_id)
        if graph and any(call['callee'] == consumer or call['caller'] == consumer for call in graph['calls']):
            from runtime.behavior_conversion.operation_calls import mark_assembled
            mark_assembled(conn, config.run_id, consumer)
        operation_reports.append({key: value for key, value in record.items() if key != "closure"})
    gate3 = json.dumps(operation_reports, sort_keys=True)
    if not _gate(conn, config, profile, directory, 3, gate3,
        all(item["review"]["approved"] and not item["review"]["issues"] and not item["review"]["unresolved_questions"] for item in operation_reports), "service_generation_pending"):
        return
    from runtime.service_generation import run_service_generation
    from models.migration_models import MigrationPlan
    plan = execution_plan or MigrationPlan.model_validate_json(conn.execute("SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1", (config.run_id,)).fetchone()[0])
    phase = run_service_generation(conn, config, profile, plan, directory,
        gate_checker=lambda: "service_generation_pending", operation_scoped=execution_plan is not None)
    if phase == "validation_evidence_pending":
        from runtime.finalization import run_finalization
        run_finalization(conn, config, profile, plan, directory, complete_run=execution_plan is None)
