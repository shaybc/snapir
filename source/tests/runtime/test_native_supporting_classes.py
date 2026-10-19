"""Replay missing and prohibited helper responses without weakening native boundaries."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from agents.behavior_conversion.configured_step import INSTRUCTION
from models.native_unit_bundle import NativeUnitBundle, NativeSourceFile
from runtime.behavior_conversion.bundle_output import validate_bundle, accept_bundle
from runtime.behavior_conversion.compiler_feedback import compiler_correction
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.ownership import create_native_context
from runtime.behavior_conversion.testing_contract import testing_contract as get_testing_contract
from runtime.java_toolchain import java_scope
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tests.runtime.test_behavior_conversion import profile, state
from tests.runtime.test_native_xml_build import OfflineVerifier


def failures():
    return json.loads((Path(__file__).parent / "fixtures/fraud_check_supporting_class_failures.json").read_text(encoding="utf-8"))


def test_saved_missing_helper_diagnostics_explain_companion_implementation():
    saved = failures()[0]
    feedback = compiler_correction(saved["error"], saved["response"]["files"])
    diagnostics = feedback["diagnostics"]
    assert {item["category"] for item in diagnostics} == {"missing_package", "missing_symbol"}
    for item in diagnostics:
        assert item["file"].endswith("FraudCheckStep.java")
        assert "native companion implementation" in item["correction"]
        assert "IBM import" in item["correction"]
    assert any(item["details"].get("symbol") == "class HTTPService" for item in diagnostics)
    # Identical guidance applies to an unrelated class/package, not just this fixture.
    other = compiler_correction(saved["error"].replace("HTTPService", "PaymentClient").replace("com.company.migration", "example.missing"), saved["response"]["files"])
    assert any("class PaymentClient" in item["correction"] for item in other["diagnostics"])


@pytest.mark.parametrize("index", [1, 2])
def test_ibm_helper_rejection_names_file_and_type_and_requests_native_behavior(index):
    candidate = NativeUnitBundle.model_validate(failures()[index]["response"])
    with pytest.raises(ValueError) as caught:
        validate_bundle(candidate)
    message = str(caught.value)
    assert "FraudCheckStep.java" in message and "HTTPService" in message
    assert "native companion implementation" in message
    assert "supplied supporting source evidence" in message
    assert "callers, public API metadata and tests" in message
    assert "only an interface/mock" in message


def test_op_step_request_and_correction_both_require_supporting_implementations():
    saved = failures()[1]
    candidate = NativeUnitBundle.model_validate(saved["response"])
    conn, config = state()
    requests = []
    def model(instruction, encoded):
        requests.append(json.loads(encoded))
        assert "Include native companion implementations" in instruction
        assert "invent a target package" in instruction
        assert "An interface or mock alone" in instruction
        assert requests[-1]["sources"] == saved["sources"]
        return candidate.model_dump_json()
    with pytest.raises(ValueError, match="Prohibited framework dependency"):
        generate(conn, config, profile(), "unit", "step", INSTRUCTION, {"sources": saved["sources"]},
            NativeUnitBundle, validator=lambda output, cached: validate_bundle(output), model_call=model)
    assert len(requests) == 3
    assert "native companion implementation" in requests[1]["correction_feedback"]


def test_saved_fraud_step_builds_with_evidenced_native_companion(tmp_path):
    jdk = Path("C:/Program Files/Java/jdk-25.0.3")
    if not shutil.which("mvn") or not jdk.is_dir():
        pytest.skip("Offline Maven/JDK unavailable")
    saved = failures()[2]
    candidate = NativeUnitBundle.model_validate(saved["response"])
    package = candidate.unit_contract.apis[0].type_name.rsplit(".", 1)[0]
    original = "com.ibm.il.dse.cc.service.communication.http.HTTPService"
    for file in candidate.files:
        file.content = file.content.replace(original, package + ".FraudClient").replace("HTTPService", "FraudClient")
    evidence = next(source["content"] for source in saved["sources"] if source["identity"] == original)
    companion = evidence.replace("package com.ibm.il.dse.cc.service.communication.http;", "package " + package + ";").replace("HTTPService", "FraudClient")
    candidate.files.append(NativeSourceFile(path="src/main/java/" + package.replace(".", "/") + "/FraudClient.java", content=companion))
    files = validate_bundle(candidate, candidate.unit_contract.apis, candidate.unit_contract.requirements, candidate.evidence_ids)
    settings = profile(java_version=25, java_home=str(jdk))
    verifier = OfflineVerifier()
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="native-helper-replay"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    with java_scope(settings):
        result, _ = accept_bundle(tmp_path / "fraud", files, context, settings, candidate.dependencies,
            required_tests={name for paths in candidate.coverage.values() for name in paths},
            testing_contract=get_testing_contract(settings))
    assert result["build_passed"] and result["tests_passed"] and result["test_count"] == 4
