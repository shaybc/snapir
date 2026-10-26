"""Stage immutable approved sources and generate final managed Maven services."""

from runtime.workspace_paths import run_report_path, write_run_report
import hashlib
import json
import shutil
from pathlib import Path

from models.maven_dependency import MavenDependency
from constants import JAVA_VERSION, SPRING_BOOT_VERSION
from runtime.human_gates import evaluate_gate
from runtime.managed_projects import create_build_context
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.operation_review import run_operation_review_gate
from runtime.operation_review.evidence import collect_operation_evidence
from runtime.service_generation.project_output import configure_executable_build, validate_wrapper_output
from runtime.service_generation.validation import validate_service_project
from runtime.service_generation.corrections import route_correction
from tools.maven_dependency_tools.pom_manager import merge_dependencies
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.generated_artifacts import upsert_generated_artifact
from tools.state_store_tools.runs import update_run_status
from runtime.service_generation.dependency_pins import operation_dependency_pins, apply_dependency_pins


def _project_hash(project):
    """Fingerprint build inputs without transient Maven output or audit files."""
    files = [Path(project) / "pom.xml", *sorted((Path(project) / "src").rglob("*"))]
    return hashlib.sha256(json.dumps([(str(path.relative_to(project)), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in files if path.is_file()], sort_keys=True).encode()).hexdigest()


def generation_settings_identity(profile):
    """Bind generation reuse to resolved model, build and validation settings."""
    identity = json.dumps({name: getattr(profile, name) for name in (
        "model_name", "model_provider", "model_base_url", "model_timeout_seconds",
        "max_model_attempts", "maven_settings_path", "maven_local_repository",
        "approved_maven_repository_urls", "allowed_ibm_artifacts", "allowed_ibm_classes",
        "runtime_validation_mode")}, sort_keys=True) + str(getattr(profile, "java_version", JAVA_VERSION)) + str(getattr(profile, "java_home", None)) + SPRING_BOOT_VERSION
    if profile.conversion_strategy == "behavior_units":
        from runtime.service_generation.operation_wiring import WIRING_VERSION
        identity += WIRING_VERSION
        from runtime.service_generation.response import RESPONSE_VERSION
        identity += RESPONSE_VERSION
        from runtime.service_generation.project_output import WRAPPER_OUTPUT_VERSION
        identity += WRAPPER_OUTPUT_VERSION
    if profile.service_maven_dependencies:
        identity += json.dumps({key: [pin.model_dump(mode="json") for pin in pins]
                                for key, pins in profile.service_maven_dependencies.items()}, sort_keys=True)
    return identity


def run_service_generation(conn, config, profile, plan, directory, *, gate_checker=None,
                           context_factory=create_build_context, generator=None, validator=validate_service_project, operation_scoped=False):
    """Generate each selected service with durable attempts, then persist honest validation evidence."""
    gate_checker = gate_checker or (lambda: run_operation_review_gate(conn, config, profile, plan, directory))
    if gate_checker() != "service_generation_pending":
        return "operation_gate_not_accepted"
    report = run_report_path(directory, "gate_3_report.txt").read_text(encoding="utf-8")
    if evaluate_gate(conn, config.run_id, 3, report, "human", True) != "approved":
        return "operation_gate_not_accepted"
    conn.execute("""CREATE TABLE IF NOT EXISTS service_generation_checkpoints (
        run_id TEXT, operation_id TEXT, channel TEXT, input_hash TEXT, project_hash TEXT,
        attempts INTEGER NOT NULL, validation_json TEXT, PRIMARY KEY(run_id,operation_id,channel))""")
    conn.commit()
    update_run_status(conn, config.run_id, "in_progress", "service_generation")
    outcomes = []
    correction_phase = None
    retry_generation = False
    operation_evidence = collect_operation_evidence(conn, config, profile, plan)
    if profile.conversion_strategy == 'behavior_units':
        from runtime.behavior_conversion.operation_calls import order_closures
        operation_evidence = order_closures(conn, config, operation_evidence)
    for item in operation_evidence:
        key = (config.run_id, item["operation_id"], item["channel"])
        dependency_pins = operation_dependency_pins(profile, item["channel"], item["operation_id"])
        project = Path(directory) / "services" / item["channel"] / item["operation_id"]
        task_id = "service-" + hashlib.sha256(":".join(key).encode()).hexdigest()
        identity = hashlib.sha256((item["fingerprint"] + report + generation_settings_identity(profile)).encode()).hexdigest()
        row = conn.execute("SELECT * FROM service_generation_checkpoints WHERE run_id=? AND operation_id=? AND channel=?", key).fetchone()
        attempts = row["attempts"] if row and row["input_hash"] == identity else 0
        result = None
        output = None
        try:
            if item["issues"]:
                raise ValueError("; ".join(item["issues"]))
            cached = json.loads(row["validation_json"]) if row else {}
            if (row and row["input_hash"] == identity and row["project_hash"] and
                    cached.get("package_passed") and cached.get("test_status") in {"passed", "not_available"} and
                    _project_hash(project) == row["project_hash"]):
                result = json.loads(row["validation_json"])
            else:
                if attempts >= config.max_agent_task_retries:
                    raise ValueError("Service generation retry limit reached")
                attempts += 1
                conn.execute("INSERT OR REPLACE INTO service_generation_checkpoints VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (*key, identity, "", attempts, "{}"))
                conn.commit()
                protected = {str(path.relative_to(item["project"])).replace("\\", "/"): path.read_text(encoding="utf-8")
                             for path in (Path(item["project"]) / "src/main/java").rglob("*.java")}
                # Only this runtime-owned final workspace is reset; reviewed projects remain intact.
                if project.exists():
                    if not project.resolve().is_relative_to((Path(directory) / "services").resolve()) or project.is_symlink():
                        raise ValueError("Unsafe final project path")
                    shutil.rmtree(project)
                project.mkdir(parents=True)
                shutil.copyfile(Path(item["project"]) / "pom.xml", project / "pom.xml")
                artifact = item['operation_id']
                if item.get('payload', {}).get('scoped_operation_identity'):
                    from runtime.scoped_native.project_names import native_artifact_id
                    artifact = native_artifact_id(artifact)
                context = context_factory(profile, project, artifact)
                payload = dict(operation=item["payload"], approved_sources=protected,
                               java_version=str(profile.java_version), spring_boot_version=SPRING_BOOT_VERSION,
                               pom=(project / "pom.xml").read_text(encoding="utf-8"),
                               validation_feedback=cached if row and row["input_hash"] == identity else {})
                if dependency_pins:
                    payload["pinned_dependencies"] = [pin.model_dump(mode="json") for pin in dependency_pins]
                if item['payload'].get('service_connections'):
                    from runtime.behavior_conversion.connection_contract import attach_connections
                    attach_connections(payload, item['payload']['service_connections'])
                if profile.conversion_strategy == "behavior_units":
                    from runtime.service_generation.operation_wiring import WIRING_INSTRUCTION, WIRING_VERSION
                    payload["production_wiring_requirement"] = dict(version=WIRING_VERSION, description=WIRING_INSTRUCTION)
                previous = conn.execute("SELECT output_json FROM agent_tasks WHERE task_id=?", (task_id,)).fetchone()
                if previous and row and row["input_hash"] == identity:
                    payload["previous_generation"] = json.loads(previous[0]).get("generation_output")
                if cached.get("response_correction") and row and row["input_hash"] == identity:
                    from runtime.service_generation.response import attach_response_correction
                    attach_response_correction(payload, cached)
                if profile.conversion_strategy == "behavior_units":
                    from runtime.service_generation.correction_payload import deduplicate_generation_correction
                    payload = deduplicate_generation_correction(payload)
                if generator is None:
                    if profile.model_provider == "mock":
                        raise ValueError("Mock service generation requires explicit fixtures")
                    instruction = 'Generate Spring Boot wrappers and tests around the supplied immutable Java sources. Address all validation_feedback using previous_generation when supplied. Return JSON with files (relative source/resource path to content) and dependencies (group_id, artifact_id, version, scope, reason, required_classes). Do not return a POM, binary files or alter approved sources. Include Application.java, controller, xml/JaxbConfig.java, error/GlobalExceptionHandler.java and application.properties. Delegate business logic to the supplied service. Use Java java_version and pin every Spring Boot dependency to spring_boot_version from the supplied JSON. Use pinned verified Maven dependency proposals.'
                    if dependency_pins:
                        instruction += ' Use pinned_dependencies for their exact artifact versions and scopes; do not substitute guessed versions. Preserve their required_classes.'
                    if payload.get('native_http_contract'):
                        from runtime.behavior_conversion.operation_calls import INSTRUCTION as OPERATION_CALL_INSTRUCTION
                        instruction += '\n' + OPERATION_CALL_INSTRUCTION
                    if profile.conversion_strategy == "behavior_units":
                        instruction = instruction.replace('xml/JaxbConfig.java', 'Jackson XML message-converter configuration')
                        instruction += "\n" + WIRING_INSTRUCTION
                        if payload.get('service_connections'):
                            from runtime.behavior_conversion.service_connection_evidence import SERVICE_CONNECTION_INSTRUCTION
                            instruction += '\n' + SERVICE_CONNECTION_INSTRUCTION
                        instruction += ' Accept and produce application/xml using request_wire_type, success_wire_type and error_wire_type from the supplied contract. Call the approved request mapper to produce business inputs, then the service, then the appropriate response mapper to produce wire outputs. Reuse the exact accepted unit APIs and sources; do not move formatting into business logic. No JAXB or Composer runtime. Keep the controller thin. Preserve success/error XML contracts. Do not infer authentication metadata. Include jackson-dataformat-xml and required Spring Boot dependencies. JSON support is future work. Verify JSON escaping before returning.'
                    from runtime.managed_conversion_response import _remove_response_fence
                    if profile.conversion_strategy == "behavior_units":
                        from runtime.service_generation.response import RESPONSE_INSTRUCTION
                        instruction += "\n" + RESPONSE_INSTRUCTION
                        from runtime.behavior_conversion.request_context import encode_request
                        _, encoded = encode_request(payload, instruction, profile.behavior_context_chars)
                    else:
                        encoded = json.dumps(payload)
                    response = AdkExecutor(profile).execute(instruction, encoded)
                    if profile.conversion_strategy == "behavior_units":
                        from runtime.service_generation.response import parse_service_response
                        output = parse_service_response(response)
                    else:
                        output = json.loads(response)
                else:
                    output = generator(payload)
                proposals = [MavenDependency.model_validate(value) for value in output["dependencies"]]
                if dependency_pins:
                    proposals = apply_dependency_pins(proposals, dependency_pins)
                    output["dependencies"] = [proposal.model_dump(mode="json") for proposal in proposals]
                merge_dependencies(context.pom_path, proposals, context.verifier,
                                   allowed_ibm_artifacts=context.allowed_ibm_artifacts, task_id=task_id)
                if profile.conversion_strategy == "behavior_units":
                    from runtime.service_generation.startup_resources import validate_jdbc_driver
                    validate_jdbc_driver(output["files"], proposals)
                    from runtime.service_generation.connection_wiring import validate_connection_wiring
                    validate_connection_wiring(output['files'], proposals, item['payload'].get('service_connections', []))
                    wrappers = validate_wrapper_output(output["files"], protected, item["operation_id"], context, behavior_units=True,
                                                       operation_contract=item["payload"].get("contract"))
                    if payload.get('native_http_contract'):
                        from runtime.behavior_conversion.operation_calls import validate_endpoint, validate_client_configuration
                        validate_endpoint(wrappers, payload['native_http_contract'])
                        validate_client_configuration(wrappers, payload.get('operation_calls', []))
                else:
                    wrappers = validate_wrapper_output(output["files"], protected, item["operation_id"], context)
                configure_executable_build(context)
                for name, content in {**protected, **wrappers}.items():
                    target = project / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                for name in protected:
                    shutil.copyfile(Path(item["project"]) / name, project / name)
                result = validator(project, context)
                if profile.conversion_strategy == "behavior_units":
                    from runtime.service_generation.operation_wiring import validate_wiring_execution
                    validate_wiring_execution(project, wrappers, item["payload"].get("contract"), result)
                result["generation_output"] = output
                conn.execute("UPDATE service_generation_checkpoints SET project_hash=?, validation_json=? WHERE run_id=? AND operation_id=? AND channel=?",
                             (_project_hash(project), json.dumps(result), *key))
            if result.get("build_passed") and result.get("package_passed"):
                from runtime.runtime_validation.executor import RuntimeTestExecutor
                result.update(RuntimeTestExecutor(profile).execute(item, directory))
                conn.execute("UPDATE service_generation_checkpoints SET validation_json=? WHERE run_id=? AND operation_id=? AND channel=?",
                             (json.dumps(result), *key))
            passed = result.get("build_passed") and result.get("package_passed") and result.get("ibm_guard_passed") and result.get("test_status") == "passed"
            if passed and item['payload'].get('native_http_contract'):
                from tools.state_store_tools.operation_calls import set_contract_status
                set_contract_status(conn, config.run_id, item['channel'] + '/' + item['operation_id'], 'validated')
            upsert_generated_artifact(conn, artifact_id=task_id, run_id=config.run_id, operation_id=item["operation_id"],
                channel=item["channel"], target_language="java", artifact_kind="service", generated_path=str(project),
                status="converted" if passed else "blocked", blocking_reason=None if passed else "validation_incomplete",
                attempt_number=attempts)
        except Exception as exc:
            result = dict(error=str(exc), build_passed=False, generation_output=output)
            from runtime.service_generation.response import ServiceResponseError
            if isinstance(exc, ServiceResponseError):
                result.update(response_correction=exc.feedback, previous_generation_response=exc.response)
            passed = False
        if not passed:
            conn.execute("UPDATE service_generation_checkpoints SET validation_json=? WHERE run_id=? AND operation_id=? AND channel=?",
                         (json.dumps(result), *key))
            if profile.conversion_strategy == "behavior_units":
                from runtime.behavior_conversion.corrections import route_native_correction
                route = route_native_correction(conn, config, item, result) if not item["issues"] else "human"
            else:
                route = route_correction(conn, config, item, result) if not item["issues"] else "human"
            result["correction_route"] = route
            if route == "component":
                correction_phase = "component_correction_pending"
            elif route == "assembly" and correction_phase != "component_correction_pending":
                correction_phase = "assembly_correction_pending"
            elif route == "generation" and attempts < config.max_agent_task_retries:
                retry_generation = True
        upsert_agent_task(conn, task_id=task_id, run_id=config.run_id, agent_name="ManagedServiceGeneration",
            scope_type="operation", scope_id=item["operation_id"], channel=item["channel"], target_language="java",
            status="completed" if passed else "blocked", input_data=dict(fingerprint=identity), output_data=result,
            max_retries=config.max_agent_task_retries)
        outcomes.append(dict(operation_id=item["operation_id"], channel=item["channel"], project=str(project),
                             passed=bool(passed), validation=result))
        conn.commit()
    fresh = collect_operation_evidence(conn, config, profile, plan)
    expected = [(value["operation_id"], value["channel"],
                 hashlib.sha256((value["fingerprint"] + report + generation_settings_identity(profile)).encode()).hexdigest()) for value in fresh]
    recorded = conn.execute("SELECT operation_id,channel,input_hash FROM service_generation_checkpoints WHERE run_id=?",
                            (config.run_id,)).fetchall()
    if operation_scoped:
        selected = {(packet.operation_id, packet.channel) for batch in plan.batches for packet in batch.task_packets}
        recorded = [row for row in recorded if (row[0], row[1]) in selected]
    unchanged = set(expected) == {tuple(value) for value in recorded} and all(not value["issues"] for value in fresh)
    phase = "validation_evidence_pending" if unchanged and outcomes and all(value["passed"] for value in outcomes) else "service_generation_blocked"
    if correction_phase:
        phase = correction_phase
    write_run_report(directory, "service_validation_results.json", json.dumps(outcomes, indent=2))
    update_run_status(conn, config.run_id, "paused" if phase == "validation_evidence_pending" else "blocked", phase)
    if retry_generation and not correction_phase:
        return run_service_generation(conn, config, profile, plan, directory, gate_checker=gate_checker,
            context_factory=context_factory, generator=generator, validator=validator, operation_scoped=operation_scoped)
    return phase
