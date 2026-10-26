"""Verify central format examples, correction delivery and the latest Jackson API failure."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.native_unit_bundle import NativeUnitBundle
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.format_reference_example import attach_format_reference_example
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.compatibility import compatibility_fingerprint
from runtime.behavior_conversion.compiler_feedback import compiler_correction, CompilerCorrectionError
from runtime.behavior_conversion.test_feedback import TestCorrectionError as FailureCorrectionError
from runtime.behavior_conversion.bundle_output import accept_bundle
from runtime.behavior_conversion.ownership import create_native_context
from runtime.behavior_conversion.testing_contract import testing_contract as get_testing_contract
from runtime.java_toolchain import java_scope
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tests.runtime.test_behavior_conversion import state, profile, bundle
from tests.runtime.test_native_xml_build import OfflineVerifier


def failures():
    return json.loads((Path(__file__).parent / "fixtures/transfer_response_jackson_api_failures.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", ["request_unformat", "response_format"])
def test_every_initial_and_correction_request_receives_the_same_working_example(kind):
    conn, config = state()
    saved = failures()
    requests = []
    def model(instruction, encoded):
        request = json.loads(encoded)
        requests.append(request)
        assert "Follow format_reference_example" in instruction
        files = request["format_reference_example"]["files"]
        assert len(files) == 2
        main = next(file["content"] for file in files if file["path"].startswith("src/main/"))
        assert "ToXmlGenerator.Feature.WRITE_XML_DECLARATION" in main
        assert "SerializationFeature.WRITE_XML_DECLARATION" not in main
        return json.dumps(saved[len(requests) - 1]["response"])
    def validate(candidate, cached):
        error = saved[len(requests) - 1]["error"]
        context = compiler_correction(error, [file.model_dump() for file in candidate.files])
        raise CompilerCorrectionError(error, context)
    with pytest.raises(CompilerCorrectionError):
        generate(conn, config, profile(max_agent_task_retries=len(saved)), "unit", "format", "Convert", {"kind": kind}, NativeUnitBundle,
            validator=validate, model_call=model)
    assert len(requests) == 3
    assert requests[0]["format_reference_example"] == requests[1]["format_reference_example"] == requests[2]["format_reference_example"]
    assert requests[1]["compiler_correction"]["diagnostics"]


def test_op_steps_and_services_do_not_receive_format_examples():
    for kind in ("configured_step", "service"):
        payload = {"kind": kind}
        assert not attach_format_reference_example(payload)
        assert "format_reference_example" not in payload


def test_guidance_does_not_change_known_pins_or_accepted_behavior_fingerprint():
    settings = profile()
    payload = {"kind": "response_format", "known_dependencies": [dict(group_id="example", artifact_id="api", version="9", scope="compile")]}
    original = compatibility_fingerprint("unit", payload, settings, bundle().model_dump(), [])
    attach_format_reference_example(payload)
    assert payload["known_dependencies"][0]["version"] == "9"
    assert compatibility_fingerprint("unit", payload, settings, bundle().model_dump(), []) == original
    payload["format_reference_example"]["files"][0]["content"] += "\n// wording clarification"
    assert compatibility_fingerprint("unit", payload, settings, bundle().model_dump(), []) == original


@pytest.mark.parametrize("fixture", ["central_example", "latest_failure"])
def test_real_java25_example_and_latest_corrected_response(fixture, tmp_path):
    jdk = Path("C:/Program Files/Java/jdk-25.0.3")
    if not shutil.which("mvn") or not jdk.is_dir():
        pytest.skip("Offline Maven/JDK unavailable")
    settings = profile(java_version=25, java_home=str(jdk))
    verifier = OfflineVerifier()
    if fixture == "central_example":
        payload = {"kind": "response_format"}
        attach_format_reference_example(payload)
        files = {file["path"]: file["content"] for file in payload["format_reference_example"]["files"]}
        dependencies = [MavenDependency(group_id="com.fasterxml.jackson.dataformat", artifact_id="jackson-dataformat-xml",
            version="2.15.2", reason="Verified format example")]
    else:
        candidate = NativeUnitBundle.model_validate(failures()[2]["response"])
        files = {file.path: file.content for file in candidate.files}
        dependencies = candidate.dependencies
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="format-reference-verification"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    def build(name):
        return accept_bundle(tmp_path / name, files, context, settings, dependencies,
            required_tests={name for name in files if name.startswith("src/test/java/")},
            testing_contract=get_testing_contract(settings))
    with java_scope(settings):
        if fixture == "latest_failure":
            with pytest.raises(CompilerCorrectionError, match="WRITE_XML_DECLARATION"):
                build("original")
            files = {name: content.replace("SerializationFeature.WRITE_XML_DECLARATION", "com.fasterxml.jackson.dataformat.xml.ser.ToXmlGenerator.Feature.WRITE_XML_DECLARATION")
                .replace("SerializationFeature.WRITE_DOC_DECLARATION", "com.fasterxml.jackson.dataformat.xml.ser.ToXmlGenerator.Feature.WRITE_XML_DECLARATION")
                for name, content in files.items()}
            # The corrected API compiles; existing malformed namespace mapping remains
            # a separate executable-test failure, rather than a false acceptance.
            with pytest.raises(FailureCorrectionError, match="Unexpected character") as caught:
                build("verified")
            assert caught.value.test_correction["diagnostics"][0]["test_method"] == "testNilDecoratorFormat"
            return
        result, _ = build("verified")
    assert result["build_passed"] and result["tests_passed"]
    assert result["test_count"] == 6
