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
    """Use durable bounded corrections; validators run before a result is accepted."""
    from runtime.behavior_conversion.compatibility import (versioned_requirements, compatibility_fingerprint,
        accepted_compatibility, save_compatibility)
    payload = dict(payload)
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
            instruction = reuse_known_dependencies(instruction, payload.get("known_dependencies", []),
                                                   java_version=profile.java_version)
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
        compatible, compatibility = accepted_compatibility(conn, config.run_id, category, identity,
            prior, output.model_dump(mode="json"), base, profile, requirements)
        if prior["fingerprint"] == fingerprint or compatible:
            if validator:
                validator(output, cached=True)
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
    if previous and previous["error"]:
        request.update(previous_model_response=previous["response"], correction_feedback=previous["error"])
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
            response = model_call(instruction, encoded)
            progress_token = begin_progress(executor.component_label)
            with progress_step("Validating JSON, testing policy and behavior coverage"):
                output = schema.model_validate_json(clean_structural_escapes(_remove_response_fence(response)))
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
            conn.execute("UPDATE behavior_attempts SET response=? WHERE run_id=? AND category=? AND identity=? AND fingerprint=? AND attempt=?",
                         (response, config.run_id, category, identity, fingerprint, attempts))
            save(conn, config.run_id, category, identity, fingerprint, output.model_dump(mode="json"))
            compatibility = compatibility_fingerprint(category, base, profile, output.model_dump(mode="json"), requirements)
            save_compatibility(conn, config.run_id, category, identity, fingerprint, compatibility, requirements)
            record("completed", attempts - start, output.model_dump(mode="json"),
                   compatibility_fingerprint=compatibility)
            return output, fingerprint
        except Exception as exc:
            error = str(exc)
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
            if response is None or attempts >= limit:
                raise
            logging.getLogger(__name__).warning("%s: requesting corrected JSON, API or build output: %s", executor.component_label, error)
            request.update(previous_model_response=response, correction_feedback=error)
        finally:
            if progress_token is not None:
                end_progress(progress_token)


def bounded_unit_evidence(conn, config, profile, unit, model_call=None):
    """Use full source when it fits, otherwise retain persisted evidence summaries."""
    data = unit.model_dump(mode="json")
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
