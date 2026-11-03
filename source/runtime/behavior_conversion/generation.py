"""Persist bounded model attempts and accept only schema-validated task results."""

import json
import logging
from pydantic import BaseModel, ConfigDict, Field
from runtime.managed_conversion_response import _remove_response_fence
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.behavior_conversion.request_context import encode_request, source_parts
from tools.state_store_tools.behavior_units import snapshot, save
from tools.state_store_tools._json import utc_now
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.agent_tasks import upsert_agent_task
from runtime.behavior_conversion.response_json import clean_structural_escapes, JSON_INSTRUCTION
from runtime.behavior_conversion.resume_budget import attempt_window
from runtime.behavior_conversion.validation_progress import begin_progress, end_progress, progress_step
from runtime.behavior_conversion.test_feedback import test_correction, TEST_CORRECTION_INSTRUCTION
from runtime.behavior_conversion.compiler_feedback import (CORRECTION_INSTRUCTION, compiler_correction, with_dependency_apis, request_dependency_apis)


class EvidenceSummary(BaseModel):
    """Findings from a bounded source excerpt; unknowns remain explicitly visible."""

    model_config = ConfigDict(extra="forbid")
    findings: list[str] = Field(min_length=1)
    unresolved_questions: list[str] = Field(default_factory=list)


def generate(conn, config, profile, category, identity, instruction, payload, schema,
             validator=None, model_call=None, label="", require_coverage=True):
    """Keep normal generation strict; opt into isolated recovery only for retained IBM dependencies."""
    from runtime.dependency_policy import dependency_policy_scope
    with dependency_policy_scope(conn,config.run_id,profile,payload):
        try:
            if profile.staged_unit_conversion:
                from runtime.behavior_conversion.conversion_tasks import conversion_task
                task=conversion_task(category,schema)
                if task!='metadata':
                    if payload.get('kind')=='thin_path_experiment' and schema.__name__=='NativeUnitBundle':
                        from runtime.behavior_conversion.staged_conversion import staged_generate
                        return staged_generate(conn,config,profile,category,identity,instruction,payload,schema,
                            validator=validator,model_call=model_call,label=label,require_coverage=require_coverage,
                            implementation_attempt=getattr(validator,'implementation_attempt',None))
                    from runtime.behavior_conversion.staged_pipeline import staged_pipeline
                    return staged_pipeline(conn,config,profile,category,identity,payload,schema,validator,model_call,task,label)
            return _generate(conn,config,profile,category,identity,instruction,payload,schema,
                validator=validator,model_call=model_call,label=label,require_coverage=require_coverage)
        except Exception as error:
            from runtime.behavior_conversion.side_road_policy import ForbiddenFrameworkDependency
            if not (profile.side_road_conversion and isinstance(error,ForbiddenFrameworkDependency)
                    and schema.__name__=='NativeUnitBundle' and not category.startswith('side_road_')):
                raise
            from runtime.behavior_conversion.side_road_conversion import recover_unit
            return recover_unit(conn,config,profile,category,identity,payload,schema,validator,model_call,error,
                generate_stage=_generate,require_coverage=require_coverage)


def _generate(conn, config, profile, category, identity, instruction, payload, schema,
              validator=None, model_call=None, label="", require_coverage=True):
    """Use durable bounded corrections; validators run before a result is accepted."""
    from tools.conversion_tools.scoped_workflow.preparation import is_scoped_run
    scoped_binding = None
    component_task = category == 'component_generation'
    from runtime.behavior_conversion.stage_scope import verify_stage
    if verify_stage(conn,config,profile,category,identity):
        component_task=False  # Child schemas are not component/unit acceptance records.
    elif component_task:
        from runtime.component_conversion.scope import require_component_task
        require_component_task(conn, config, profile, identity, payload)
    elif is_scoped_run(conn, config.run_id):
        from runtime.scoped_native.scope import require_task
        scoped_binding = require_task(conn, config, profile, category, identity, payload)
    from runtime.behavior_conversion.compatibility import (versioned_requirements, compatibility_fingerprint,
        accepted_compatibility, save_compatibility)
    payload = dict(payload)
    from runtime.behavior_conversion.typed_boundaries import attach_typed_boundary, validate_typed_boundary, INSTRUCTION as TYPED_BOUNDARY_INSTRUCTION
    if schema.__name__ == 'NativeUnitBundle' and attach_typed_boundary(payload):
        instruction += '\n' + TYPED_BOUNDARY_INSTRUCTION
    phase = payload.get("assembly_phase")
    if phase in {"implementation_compile", "route_test_plan"}:
        payload.pop("testing_contract", None)
    if not require_coverage:
        payload["coverage_owner"] = "application; tests and coverage are validated in the scenario/final acceptance phases"
    requirements = versioned_requirements(profile, category, payload)
    platform_requirement = payload.get("testing_contract", {}).get("requirement", {}).get("requirement_id")
    behavior_requirements = [item for item in requirements if item["requirement_id"] != platform_requirement]
    payload["versioned_requirements"] = requirements
    if requirements:
        payload["requirements"] = {item["requirement_id"]: item["description"] for item in behavior_requirements}
    if schema.__name__ == "NativeUnitBundle":
        from runtime.behavior_conversion.format_reference_example import attach_format_reference_example, FORMAT_EXAMPLE_INSTRUCTION
        if attach_format_reference_example(payload):
            instruction += "\n" + FORMAT_EXAMPLE_INSTRUCTION
        from agents.behavior_conversion.native_instructions import reuse_known_dependencies
        if phase == "implementation_compile":
            from agents.behavior_conversion.operation_route_tests import implementation_dependencies
            instruction += "\n" + implementation_dependencies(profile.java_version)
        else:
            dependency_instruction = instruction
            instruction = reuse_known_dependencies(instruction, payload.get("known_dependencies", []),
                                                   java_version=profile.java_version)
            if scoped_binding:
                normalized_dependency_instruction = reuse_known_dependencies(dependency_instruction, [],
                                                                            java_version=profile.java_version)
                dependency_instruction_actual = instruction
        if payload.get("testing_contract"):
            instruction += "\nFollow the versioned testing_contract, its pinned dependencies and reference examples. Keep tests focused, separate business and adapter tests, and mock external interfaces instead of hand implementing them. Example values are illustrative only; derive assertions from the original evidence."
        if phase in {"implementation_compile", "single_route_test"}:
            from agents.behavior_conversion.operation_route_tests import IMPLEMENTATION_COMPILER, SCENARIO_COMPILER
            instruction += "\n" + (IMPLEMENTATION_COMPILER if phase == "implementation_compile" else SCENARIO_COMPILER)
        else:
            instruction += "\n" + CORRECTION_INSTRUCTION
            instruction += "\n" + TEST_CORRECTION_INSTRUCTION
        if require_coverage:
            instruction += "\nHonor every versioned_requirements ID and version. Provide executable coverage for the meaningful behavior obligations in requirements; one focused test may cover multiple source files. DTOs, getters, configuration and forwarding helpers do not each need separate tests when their behavior is exercised through mapper, workflow or caller tests. The testing_contract platform policy is validated directly through dependencies, source safeguards and the build; do not add a platform coverage entry or declare it in unit_contract.requirements. Changing metadata alone does not satisfy a changed behavior requirement."
        else:
            instruction += "\nHonor the versioned requirements for this phase. Do not generate coverage metadata; the application derives coverage from separately accepted scenario tests before final operation acceptance. The testing platform is checked directly, not through coverage entries."
    if payload.get('service_connections') or payload.get('unit', {}).get('service_connections'):
        from runtime.behavior_conversion.service_connection_evidence import SERVICE_CONNECTION_INSTRUCTION
        instruction += '\n' + SERVICE_CONNECTION_INSTRUCTION
    if payload.get('operation_calls') or payload.get('unit', {}).get('operation_calls') or payload.get('native_http_contract'):
        from runtime.behavior_conversion.operation_calls import INSTRUCTION as OPERATION_CALL_INSTRUCTION
        instruction += '\n' + OPERATION_CALL_INSTRUCTION
    instruction = instruction + "\n" + JSON_INSTRUCTION
    request = dict(payload, schema=schema.model_json_schema())
    base, encoded = encode_request(request, instruction, profile.behavior_context_chars)
    settings = {name: getattr(profile, name) for name in ("java_version", "java_home", "model_name", "model_provider",
        "model_base_url", "model_timeout_seconds", "max_model_attempts", "maven_settings_path", "maven_local_repository",
        "approved_maven_repository_urls", "allowed_ibm_artifacts", "allowed_ibm_classes", "behavior_context_chars")}
    fingerprint = stable_id(category, instruction, base, settings, "behavior-v1")
    if scoped_binding:
        from runtime.scoped_native.results import fingerprint_payload
        fingerprint_instruction = instruction
        if schema.__name__ == 'NativeUnitBundle' and phase != 'implementation_compile':
            fingerprint_instruction = normalized_dependency_instruction + instruction[len(dependency_instruction_actual):]
        fingerprint = stable_id(category, fingerprint_instruction,
            json.dumps(fingerprint_payload(base, category), sort_keys=True), settings, 'scoped-behavior-v1')
    def record(status, attempt=0, output=None, error=None, request_fingerprint=None, compatibility_fingerprint=None):
        upsert_agent_task(conn, run_id=config.run_id, agent_name="BehaviorConversion",
            scope_type=category, scope_id=identity, channel="", target_language="java",
            status=status, attempt_number=attempt, max_retries=profile.max_agent_task_retries,
            input_data={"fingerprint": request_fingerprint or fingerprint,
                        "request_fingerprint": request_fingerprint or fingerprint,
                        "compatibility_fingerprint": compatibility_fingerprint}, output_data=output, error_message=error)
    prior = snapshot(conn, config.run_id, category, identity)
    if prior and prior["status"] == "accepted":
        output = schema.model_validate_json(prior["data_json"])
        compatibility = None
        if scoped_binding:
            from runtime.scoped_native.results import cached_result
            reusable = prior['fingerprint'] == fingerprint and cached_result(
                scoped_binding, conn, config, profile, category, identity, fingerprint, output.model_dump(mode='json'))
        elif component_task:
            reusable = prior['fingerprint'] == fingerprint
        else:
            compatible, compatibility = accepted_compatibility(conn, config.run_id, category, identity,
                prior, output.model_dump(mode="json"), base, profile, requirements)
            reusable = prior["fingerprint"] == fingerprint or compatible
        if reusable:
            if hasattr(output,'files'):validate_typed_boundary(output, payload.get('typed_boundary_contract'))
            if component_task:
                require_component_task(conn, config, profile, identity, payload)
            if validator:
                validator(output, cached=True)
            if not scoped_binding and not component_task:
                save_compatibility(conn, config.run_id, category, identity, prior["fingerprint"], compatibility, requirements)
            record("completed", output=output.model_dump(mode="json"),
                   request_fingerprint=prior["fingerprint"], compatibility_fingerprint=compatibility)
            return output, prior["fingerprint"]
    executor = AdkExecutor(profile)
    executor.component_label = label or category + ": " + identity
    if model_call is None:
        if profile.model_provider == "mock":
            raise ValueError("Behavior-unit mock execution requires explicit model fixtures")
        model_call = executor.execute
    previous = conn.execute("SELECT attempt,response,error,request_json FROM behavior_attempts WHERE run_id=? AND category=? AND identity=? AND fingerprint=? ORDER BY attempt DESC LIMIT 1",
                            (config.run_id, category, identity, fingerprint)).fetchone()
    attempts = previous["attempt"] if previous else 0
    start, limit = attempt_window(config.run_id, category, identity, fingerprint, attempts,
                                  profile.max_agent_task_retries)
    from runtime.behavior_conversion.verification_mode import executable_mode
    if previous and previous["error"] and (previous['response'] is not None or not executable_mode(profile)):
        request.update(previous_model_response=previous["response"], correction_feedback=previous["error"])
        stored_verification = json.loads(previous['request_json']).get('failed_verification_context')
        if stored_verification:
            request['verification_feedback'] = stored_verification
        stored = json.loads(previous["request_json"]).get("failed_compiler_context")
        stored_test = json.loads(previous["request_json"]).get("failed_test_context")
        if stored_test:
            request["test_correction"] = with_dependency_apis(stored_test, request_dependency_apis(request))
        if stored:
            request["compiler_correction"] = with_dependency_apis(stored, request_dependency_apis(request))
        else:
            try:
                failed = schema.model_validate_json(clean_structural_escapes(_remove_response_fence(previous["response"] or "")))
                correction = compiler_correction(previous["error"],
                    [item.model_dump() for item in getattr(failed, "files", [])], request_dependency_apis(request))
                if correction:
                    request["compiler_correction"] = correction
                elif not stored_test:
                    correction = test_correction(previous["error"],
                        [item.model_dump() for item in getattr(failed, "files", [])], request_dependency_apis(request))
                    if correction:
                        request["test_correction"] = correction
            except ValueError:
                pass
    if attempts >= limit:
        raise ValueError("Behavior task correction limit reached: " + identity + "; resume explicitly to retry")
    while attempts < limit:
        attempts += 1
        actual, encoded = encode_request(request, instruction, profile.behavior_context_chars)
        conn.execute("INSERT INTO behavior_attempts VALUES (?,?,?,?,?,?,?,?,?)",
                     (config.run_id, category, identity, fingerprint, attempts, json.dumps(actual), None, None, utc_now()))
        conn.commit()
        record("started", attempts - start)
        response = None
        output = None
        progress_token = None
        try:
            if component_task:
                require_component_task(conn, config, profile, identity, payload)
            if scoped_binding:
                from runtime.scoped_native.scope import require_task
                require_task(conn, config, profile, category, identity, payload)
            response = model_call(instruction, encoded)
            progress_token = begin_progress(executor.component_label)
            with progress_step("Validating JSON, testing policy and behavior coverage"):
                output = schema.model_validate_json(clean_structural_escapes(_remove_response_fence(response)))
                if hasattr(output,'files'):validate_typed_boundary(output, payload.get('typed_boundary_contract'))
                if schema.__name__ == "NativeUnitBundle":
                    if request.get("testing_contract"):
                        from runtime.behavior_conversion.testing_contract import validate_testing_contract
                        validate_testing_contract(output, request["testing_contract"])
                    files = {item.path for item in output.files if item.path.startswith("src/test/java/")}
                    for requirement in (behavior_requirements if require_coverage else []):
                        paths = output.coverage.get(requirement["requirement_id"], [])
                        if not paths or not set(paths).issubset(files):
                            raise ValueError("Missing test coverage for versioned requirement: " + requirement["requirement_id"])
                    if output.unit_contract and not {item["requirement_id"] for item in behavior_requirements}.issubset(output.unit_contract.requirements):
                        raise ValueError("Native contract must declare all versioned behavior requirements")
            if validator:
                validator(output, cached=False)
            if component_task:
                require_component_task(conn, config, profile, identity, payload)
            if scoped_binding:
                from runtime.scoped_native.scope import require_task
                from runtime.scoped_native.results import record_result
                require_task(conn, config, profile, category, identity, payload)
                record_result(scoped_binding, conn, config, profile, category, identity, fingerprint,
                              output.model_dump(mode='json'))
            conn.execute("UPDATE behavior_attempts SET response=? WHERE run_id=? AND category=? AND identity=? AND fingerprint=? AND attempt=?",
                         (response, config.run_id, category, identity, fingerprint, attempts))
            save(conn, config.run_id, category, identity, fingerprint, output.model_dump(mode="json"))
            compatibility = None
            if not scoped_binding:
                compatibility = compatibility_fingerprint(category, base, profile, output.model_dump(mode="json"), requirements)
                save_compatibility(conn, config.run_id, category, identity, fingerprint, compatibility, requirements)
            record("completed", attempts - start, output.model_dump(mode="json"),
                   compatibility_fingerprint=compatibility)
            return output, fingerprint
        except Exception as exc:
            from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
            error = str(exc)
            if getattr(exc, 'verification_feedback', None):
                actual['failed_verification_context'] = exc.verification_feedback
                conn.execute("UPDATE behavior_attempts SET request_json=? WHERE run_id=? AND category=? AND identity=? AND fingerprint=? AND attempt=?",
                    (json.dumps(actual), config.run_id, category, identity, fingerprint, attempts))
            if schema.__name__ == "NativeUnitBundle" and payload.get("kind") in ("request_unformat", "response_format"):
                from agents.behavior_conversion.format_mapping import XML_NULL_MAPPING_GUIDANCE
                error += "\n" + XML_NULL_MAPPING_GUIDANCE
            correction = getattr(exc, "compiler_correction", None)
            if correction:
                correction = with_dependency_apis(correction, request_dependency_apis(request))
            else:
                correction = compiler_correction(error,
                    [item.model_dump() for item in getattr(output, "files", [])], request_dependency_apis(request))
            request.pop("compiler_correction", None)
            request.pop("test_correction", None)
            test_feedback = getattr(exc, "test_correction", None)
            if test_feedback is None and correction is None:
                test_feedback = test_correction(error,
                    [item.model_dump() for item in getattr(output, "files", [])], request_dependency_apis(request))
            if test_feedback:
                test_feedback = with_dependency_apis(test_feedback, request_dependency_apis(request))
                request["test_correction"] = test_feedback
                actual["failed_test_context"] = test_feedback
                conn.execute("UPDATE behavior_attempts SET request_json=? WHERE run_id=? AND category=? AND identity=? AND fingerprint=? AND attempt=?",
                             (json.dumps(actual), config.run_id, category, identity, fingerprint, attempts))
            if correction:
                request["compiler_correction"] = correction
                actual["failed_compiler_context"] = correction
                conn.execute("UPDATE behavior_attempts SET request_json=? WHERE run_id=? AND category=? AND identity=? AND fingerprint=? AND attempt=?",
                             (json.dumps(actual), config.run_id, category, identity, fingerprint, attempts))
            conn.execute("UPDATE behavior_attempts SET response=?,error=? WHERE run_id=? AND category=? AND identity=? AND fingerprint=? AND attempt=?",
                         (response, error, config.run_id, category, identity, fingerprint, attempts))
            save(conn, config.run_id, category, identity, fingerprint, {}, "failed", error)
            record("failed", attempts - start, error=error)
            if isinstance(exc, VerificationIncomplete):
                raise
            if getattr(exc,'staged_retry_owner',None) in {'implementation','adapter'}:
                raise
            if response is None or attempts >= limit:
                raise
            logging.getLogger(__name__).warning("%s: requesting corrected JSON, API or build output: %s", executor.component_label, error)
            request.update(previous_model_response=response, correction_feedback=error)
            if getattr(exc, 'verification_feedback', None):
                request['verification_feedback'] = exc.verification_feedback
        finally:
            if progress_token is not None:
                end_progress(progress_token)


def bounded_unit_evidence(conn, config, profile, unit, model_call=None):
    """Use full source when it fits, otherwise retain persisted evidence summaries."""
    data = unit.model_dump(mode="json")
    if profile.staged_unit_conversion:return data  # Never replace implementation evidence with AI summaries.
    # Reserve half the request for schema, contracts, correction and semantic context.
    if len(json.dumps(data, ensure_ascii=False)) < profile.behavior_context_chars // 2:
        return data
    from runtime.behavior_conversion.request_context import bundle_parts
    summaries = []
    instruction = "Analyze this part of a complete configured behavior bundle. Use its XML and supporting classes together; record transformations, data reads/writes, dependency calls, outcomes and uncertainties. Return schema JSON, not code."
    for part in bundle_parts(data, instruction, EvidenceSummary.model_json_schema(), profile.behavior_context_chars // 2):
        summary, _ = generate(conn, config, profile, "analysis", stable_id(unit.fingerprint, part),
            instruction, part, EvidenceSummary, model_call=model_call,
            label=f"Oversized bundle {unit.logical_id}, part {part['part']}/{part['total_parts']}")
        summaries.append(dict(part=part["part"], evidence_ids=[source["identity"] for source in part["sources"]],
                              summary=summary.model_dump(mode="json")))
    data["sources"] = []
    data["source_summaries"] = summaries
    return data
