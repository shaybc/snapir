"""Verify the Java 25 platform and replay the ExecuteTransfer mocking failures."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.native_unit_bundle import NativeUnitBundle
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.testing_contract import (testing_contract as get_testing_contract, attach_testing_contract,
    validate_testing_contract, apply_test_platform)
from runtime.behavior_conversion.compatibility import versioned_requirements
from runtime.behavior_conversion.bundle_output import accept_bundle, validate_bundle
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.ownership import create_native_context
from runtime.java_toolchain import java_scope
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom, merge_dependencies
from tests.runtime.test_behavior_conversion import state, profile, bundle
from tests.runtime.test_native_xml_build import OfflineVerifier


def failures():
    return json.loads((Path(__file__).parent / "fixtures/execute_transfer_test_failures.json").read_text(encoding="utf-8"))


def test_latest_failures_receive_specific_generic_template_feedback():
    contract = get_testing_contract(profile(java_version=25))
    for index, saved in enumerate(failures()):
        candidate = NativeUnitBundle.model_validate(saved["response"])
        with pytest.raises(ValueError) as caught:
            validate_testing_contract(candidate, contract)
        if index == 0:
            assert "requires version=5.23.0 scope=test" in str(caught.value)
            assert "got version=5.5.0" in str(caught.value)
        else:
            assert "Handwritten external-interface test double" in str(caught.value)
            assert "reference examples" in str(caught.value)


@pytest.mark.parametrize("kind", ["request_unformat", "response_format", "configured_step", "service"])
def test_template_is_versioned_and_reaches_native_generation(kind):
    from agents.behavior_conversion.configured_step import INSTRUCTION
    conn, config = state()
    payload = {"kind": kind, "java_version": 25, "requirements": {"calculation": "Preserve calculation"}}
    settings = profile(java_version=25)
    attach_testing_contract(payload, settings)
    requests = []
    def model(instruction, encoded):
        request = json.loads(encoded)
        requests.append(request)
        assert "testing_contract" in instruction
        assert request["testing_contract"]["requirement"]["version"] == 1
        assert len(request["testing_contract"]["examples"]) == 2
        assert any(d["artifact_id"] == "mockito-core" and d["version"] == "5.23.0" for d in request["known_dependencies"])
        candidate = bundle()
        candidate.coverage = {name: [candidate.files[1].path] for name in request["requirements"]}
        return candidate.model_dump_json()
    generate(conn, config, settings, "unit" if kind != "service" else "service", kind, INSTRUCTION,
             payload, NativeUnitBundle, model_call=model)
    assert "java25-test-template" not in requests[0]["requirements"]
    assert any(item["requirement_id"] == "java25-test-template" for item in requests[0]["versioned_requirements"])


def test_existing_acceptance_is_invalidated_by_the_new_testing_requirement():
    conn, config = state()
    payload = {"kind": "configured_step", "java_version": 25}
    settings = profile(java_version=25)
    generate(conn, config, settings, "unit", "step", "Convert", payload, NativeUnitBundle,
             model_call=lambda *args: bundle().model_dump_json())
    attach_testing_contract(payload, settings)
    calls = []
    def model(instruction, encoded):
        calls.append(json.loads(encoded))
        candidate = bundle()
        candidate.coverage["java25-test-template"] = [candidate.files[1].path]
        return candidate.model_dump_json()
    generate(conn, config, settings, "unit", "step", "Convert", payload, NativeUnitBundle, model_call=model)
    assert len(calls) == 1
    assert get_testing_contract(profile(java_version=21)) is None


def test_platform_updates_only_approved_test_dependencies_on_a_copy(tmp_path):
    pom = tmp_path / "pom.xml"
    initialize_managed_pom(str(pom), "example", "tests", java_version=25)
    merge_dependencies(str(pom), [MavenDependency(group_id="org.mockito", artifact_id="mockito-core", version="5.5.0", scope="test", reason="Old tests"),
        MavenDependency(group_id="org.example", artifact_id="client", version="4.2", reason="Business API")], lambda d: None)
    apply_test_platform(pom, get_testing_contract(profile()), lambda d: None)
    text = pom.read_text(encoding="utf-8")
    assert "5.23.0" in text and "5.5.0" not in text and "4.2" in text


@pytest.mark.parametrize("fixture", ["reference", "execute_transfer"])
def test_real_java25_template_and_latest_mockito_tests_execute_offline(tmp_path, fixture):
    jdk = Path("C:/Program Files/Java/jdk-25.0.3")
    if not shutil.which("mvn") or not jdk.is_dir():
        pytest.skip("Offline Maven/JDK unavailable")
    settings = profile(java_version=25, java_home=str(jdk))
    contract = get_testing_contract(settings)
    verifier = OfflineVerifier()
    if fixture == "reference":
        files = {"src/test/java/example/" + item["path"]: item["content"] for item in contract["examples"]}
        dependencies = []
    else:
        candidate = NativeUnitBundle.model_validate(failures()[0]["response"])
        pins = {(d["group_id"], d["artifact_id"]): d for d in contract["dependencies"]}
        for dependency in candidate.dependencies:
            pin = pins.get((dependency.group_id, dependency.artifact_id))
            if pin:
                dependency.version, dependency.scope = pin["version"], pin["scope"]
        validate_testing_contract(candidate, contract)
        files = validate_bundle(candidate, candidate.unit_contract.apis, candidate.unit_contract.requirements, candidate.evidence_ids)
        dependencies = candidate.dependencies
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="verified-java25-template"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    with java_scope(settings):
        result, _ = accept_bundle(tmp_path / fixture, files, context, settings, dependencies,
            required_tests={name for name in files if name.startswith("src/test/java/")}, testing_contract=contract)
    assert result["build_passed"] and result["tests_passed"]
    assert result["test_count"] >= (3 if fixture == "reference" else 5)


def test_external_interface_rule_is_generic_and_allows_generated_narrow_ports():
    contract = get_testing_contract(profile())
    candidate = bundle()
    candidate.files[1].content = "package com.company.generated; import java.util.Iterator; public class StepTest { class Fake implements Iterator<String> {} }"
    with pytest.raises(ValueError, match="java.util.Iterator"):
        validate_testing_contract(candidate, contract)
    candidate.files[0].content = "package com.company.generated; public interface Step<T> { void save(T value); }"
    candidate.files[1].content = "package com.company.generated; import java.util.*; public class StepTest { class Fake implements Step<String> { public void save(String value) {} } }"
    validate_testing_contract(candidate, contract)


def test_platform_refuses_to_change_production_dependencies(tmp_path):
    pom = tmp_path / "pom.xml"
    initialize_managed_pom(str(pom), "example", "tests", java_version=25)
    merge_dependencies(str(pom), [MavenDependency(group_id="org.mockito", artifact_id="mockito-core", version="5.5.0", scope="compile", reason="Production dependency")], lambda d: None)
    original = pom.read_bytes()
    with pytest.raises(ValueError, match="non-test dependency"):
        apply_test_platform(pom, get_testing_contract(profile()), lambda d: None)
    assert pom.read_bytes() == original


@pytest.mark.parametrize("index", range(3))
def test_latest_format_responses_need_behavior_coverage_not_platform_metadata(index):
    responses = json.loads((Path(__file__).parent / "fixtures/transfer_request_platform_coverage_failures.json").read_text(encoding="utf-8"))
    candidate = NativeUnitBundle.model_validate(responses[index])
    assert "java25-test-template" not in candidate.coverage
    conn, config = state()
    settings = profile(java_version=25)
    payload = {"kind": "request_unformat", "requirements": {"business": "Preserve evidenced behavior"}}
    attach_testing_contract(payload, settings)
    def model(instruction, encoded):
        request = json.loads(encoded)
        assert "java25-test-template" not in request["requirements"]
        assert "do not add a platform coverage entry" in instruction
        return candidate.model_dump_json()
    def validate(output, cached):
        validate_bundle(output, output.unit_contract.apis, payload["requirements"], output.evidence_ids)
    result, _ = generate(conn, config, settings, "unit", "format", "Convert complete format", payload,
        NativeUnitBundle, validator=validate, model_call=model)
    assert result == candidate
    # Three production classes share one behavior test; no per-class tests are required.
    assert len([file for file in result.files if file.path.startswith("src/main/java/")]) == 3
    assert len([file for file in result.files if file.path.startswith("src/test/java/")]) == 1


def test_meaningful_behavior_still_requires_tests_with_the_platform_contract():
    conn, config = state()
    settings = profile(java_version=25)
    payload = {"kind": "configured_step", "requirements": {"calculation": "Preserve calculation"}}
    attach_testing_contract(payload, settings)
    candidate = bundle()
    candidate.files = candidate.files[:1]
    candidate.coverage = {}
    with pytest.raises(ValueError, match="Missing test coverage for versioned requirement: calculation"):
        generate(conn, config, settings, "unit", "step", "Convert", payload, NativeUnitBundle,
            model_call=lambda *args: candidate.model_dump_json())
