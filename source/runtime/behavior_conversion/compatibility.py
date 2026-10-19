"""Compare accepted behavior contracts independently of request wording and model choice."""

import json
from runtime.java_public_type import _code
from runtime.behavior_conversion.compiler_feedback import with_dependency_apis
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.behavior_units import snapshot, save

_DELIVERY_KEYS = {"previous_model_response", "correction_feedback", "compiler_correction",
    "test_correction", "failed_test_context",
    "format_reference_example", "constructor_example", "schema",
    "failed_compiler_context", "known_dependencies", "versioned_requirements",
    "behavior_review_feedback", "previous_bundle",
    "generic_method_validation", "dependency_validation", "transitive_class_validation",
    "source_comment_validation", "method_contract_validation", "fingerprint"}


def versioned_requirements(profile, category, request):
    """Give existing obligations baseline version 1 and apply explicitly scoped declarations."""
    unit = request.get("unit", request)
    kind = unit.get("kind", category)
    descriptions = dict(request.get("requirements", unit.get("requirements", {})))
    requirements = {name: dict(requirement_id=name, version=1, description=description)
                    for name, description in descriptions.items()}
    for item in getattr(profile, "conversion_requirements", []):
        if "*" in item.applies_to or kind in item.applies_to or category in item.applies_to:
            requirements[item.requirement_id] = dict(requirement_id=item.requirement_id,
                version=item.version, description=item.description)
    if request.get("required_step_dependencies") and request.get("assembly_phase"):
        from runtime.behavior_conversion.operation_dependencies import REQUIREMENT
        requirements[REQUIREMENT["requirement_id"]] = dict(REQUIREMENT)
    if request.get('service_connections') or unit.get('service_connections'):
        requirements['service_connections'] = dict(requirement_id='service_connections', version=1,
            description='Preserve source-resolved channel services, connectors, drivers and connection ownership')
    if request.get('operation_calls') or unit.get('operation_calls'):
        requirements['native-operation-calls'] = dict(requirement_id='native-operation-calls', version=1,
            description='Replace Composer dispatch with saved native HTTP contracts; test request/reply mapping, business errors, transport failures and timeouts')
    contract = unit.get("testing_contract", request.get("testing_contract"))
    if contract:
        declared = contract["requirement"]
        requirements[declared["requirement_id"]] = declared
    return list(requirements.values())


def _normalized(value):
    if isinstance(value, dict):
        return {key: sorted(item) if key == "requirements" and isinstance(item, dict) else _normalized(item)
                for key, item in sorted(value.items()) if key not in _DELIVERY_KEYS}
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    return value


def compatibility_fingerprint(category, request, profile, output, requirements):
    """Hash evidence, required APIs, used dependency pins, target and requirement versions."""
    data = dict(request)
    bundle = output if "files" in output else request.get("generated_bundle", {})
    sources = [dict(path=item["path"], content=_code(item["content"])) for item in bundle.get("files", [])]
    if "converted_dependency_apis" in data:
        data["converted_dependency_apis"] = with_dependency_apis(
            {"failed_sources": sources, "diagnostics": []}, data["converted_dependency_apis"])["relevant_dependency_apis"]
    # Newly available, unused libraries must not invalidate earlier accepted units.
    known = {(item["group_id"], item["artifact_id"]): item for item in request.get("known_dependencies", [])}
    pins = []
    for dependency in bundle.get("dependencies", []):
        current = known.get((dependency["group_id"], dependency["artifact_id"]), dependency)
        pins.append({key: current[key] for key in ("group_id", "artifact_id", "version", "scope")})
    data["used_dependency_pins"] = sorted(pins, key=lambda item: (item["group_id"], item["artifact_id"]))
    data["requirements"] = sorted(item["requirement_id"] for item in requirements)
    # Reviews contain the same unit evidence nested under unit.
    if "unit" in data:
        unit = dict(data["unit"])
        unit["requirements"] = sorted(unit.get("requirements", {}))
        if "converted_dependency_apis" in unit:
            unit["converted_dependency_apis"] = with_dependency_apis(
                {"failed_sources": sources, "diagnostics": []}, unit["converted_dependency_apis"])["relevant_dependency_apis"]
        data["unit"] = unit
    versions = {item["requirement_id"]: item["version"] for item in requirements}
    settings = {name: getattr(profile, name) for name in ("java_version", "java_home",
        "allowed_ibm_artifacts", "allowed_ibm_classes")}
    return stable_id(category, _normalized(data), versions, settings, "compatibility-v1")


def accepted_compatibility(conn, run_id, category, identity, prior, output, current, profile, requirements):
    """Bootstrap legacy acceptance only from its exact successful request and baseline requirements."""
    stored = snapshot(conn, run_id, "compatibility:" + category, identity)
    expected = compatibility_fingerprint(category, current, profile, output, requirements)
    if current.get("behavior_review_feedback"):
        accepted_request = conn.execute("SELECT request_json FROM behavior_attempts WHERE run_id=? AND category=? AND identity=? AND fingerprint=? AND error IS NULL AND response IS NOT NULL ORDER BY attempt DESC LIMIT 1",
            (run_id, category, identity, prior["fingerprint"])).fetchone()
        feedback = json.loads(accepted_request[0]).get("behavior_review_feedback") if accepted_request else None
        if feedback != current["behavior_review_feedback"]:
            return False, expected
    if stored and stored["data_json"]:
        metadata = json.loads(stored["data_json"])
        if metadata.get("request_fingerprint") == prior["fingerprint"] and stored["fingerprint"] == expected:
            return True, expected
    row = conn.execute("SELECT request_json FROM behavior_attempts WHERE run_id=? AND category=? AND identity=? AND fingerprint=? AND error IS NULL AND response IS NOT NULL ORDER BY attempt DESC LIMIT 1",
        (run_id, category, identity, prior["fingerprint"])).fetchone()
    if not row:
        return False, expected
    previous = json.loads(row["request_json"])
    old_requirements = previous.get("versioned_requirements")
    if old_requirements is None:
        unit = previous.get("unit", previous)
        old_requirements = [dict(requirement_id=name, version=1, description=description)
            for name, description in previous.get("requirements", unit.get("requirements", {})).items()]
    # Previous Java targets are stored in requests, not inferred from today's configuration.
    old_profile = profile.model_copy(update={"java_version": previous.get("java_version", profile.java_version)})
    old = compatibility_fingerprint(category, previous, old_profile, output, old_requirements)
    return old == expected, expected


def save_compatibility(conn, run_id, category, identity, request_fingerprint, fingerprint, requirements):
    """Persist the second fingerprint alongside the accepted result without altering attempt history."""
    save(conn, run_id, "compatibility:" + category, identity, fingerprint,
         dict(request_fingerprint=request_fingerprint,
              requirement_versions={item["requirement_id"]: item["version"] for item in requirements}))
