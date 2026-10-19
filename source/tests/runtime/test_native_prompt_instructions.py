"""Check first-response guidance and replay saved native conversion responses."""

import json
from pathlib import Path

import pytest
from agents.behavior_conversion.configured_step import INSTRUCTION as STEP
from agents.behavior_conversion.format_mapping import INSTRUCTION as FORMAT
from agents.behavior_conversion.native_instructions import response_example, APPROVED_JUNIT_DEPENDENCY
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.generation import generate
from tests.runtime.test_behavior_conversion import state, profile


@pytest.mark.parametrize("kind,instruction", [("step", STEP), ("format", FORMAT)])
def test_examples_match_schema_java_methods_and_first_response_rules(kind, instruction):
    example = NativeUnitBundle.model_validate(response_example(kind))
    validate_bundle(example, example.unit_contract.apis, example.unit_contract.requirements,
                    example.evidence_ids)
    assert instruction.startswith("Mandatory target-code contract for the FIRST response")
    assert "No com.ibm imports" in instruction
    assert "ANY generated main or test file" in instruction
    assert "Before returning EVERY response" in instruction
    assert "behavior evidence\nONLY" in instruction
    assert json.dumps(APPROVED_JUNIT_DEPENDENCY) in instruction
    assert json.dumps(response_example(kind)) in instruction
    assert "scope test" in instruction and "transitively" in instruction


@pytest.mark.parametrize("instruction", [STEP, FORMAT])
def test_actual_first_request_includes_guidance_and_latest_response_needs_no_json_or_api_correction(instruction):
    response = (Path(__file__).parent / "fixtures/latest_transitive_dependency_response.json").read_text(encoding="utf-8")
    conn, config = state()
    calls = []
    def model(text, payload):
        calls.append((text, json.loads(payload)))
        assert text.startswith("Mandatory target-code contract")
        assert "initial or correction" in text
        assert "junit-jupiter-api" in text
        assert "schema" in json.loads(payload)
        return response
    def validate(bundle, cached):
        validate_bundle(bundle, bundle.unit_contract.apis, bundle.unit_contract.requirements,
                        bundle.evidence_ids)
    output, _ = generate(conn, config, profile(), "unit", "replay", instruction,
                         {"unit_id": "replay"}, NativeUnitBundle, validator=validate, model_call=model)
    assert len(calls) == 1
    assert output.dependencies[0].coordinates == "org.junit.jupiter:junit-jupiter:5.10.2"
    assert output.dependencies[0].scope == "test"


def test_saved_ibm_response_remains_rejected_with_specific_feedback():
    # The saved engine response contains native code; inject its original forbidden import
    # to ensure stronger instructions have not weakened response validation.
    path = Path(__file__).parent / "fixtures/latest_transitive_dependency_response.json"
    bundle = NativeUnitBundle.model_validate_json(path.read_text(encoding="utf-8"))
    bundle.files[0].content = bundle.files[0].content.replace("import java.util.HashMap;",
        "import com.ibm.dse.base.Context;\nimport java.util.HashMap;")
    with pytest.raises(ValueError, match="Prohibited framework dependency in .*ValidationFailedStep.java"):
        validate_bundle(bundle)


@pytest.mark.parametrize("kind", ["step", "format"])
def test_examples_compile_and_execute_offline(monkeypatch, tmp_path, kind):
    import shutil
    from types import SimpleNamespace
    from runtime.java_toolchain import java_scope
    from runtime.behavior_conversion.bundle_output import accept_bundle
    from runtime.behavior_conversion.ownership import create_native_context
    from tools.maven_dependency_tools.build_context import ManagedBuildContext
    from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
    cache = Path.home() / ".m2/repository"
    jdk = Path("C:/Program Files/Java/jdk-25.0.3")
    if not shutil.which("mvn") or not jdk.is_dir():
        pytest.skip("Offline Maven/JDK is unavailable")
    verifier = MavenRepositoryVerifier(None, [], str(cache))
    original = verifier._arguments
    monkeypatch.setattr(verifier, "_arguments", lambda: original() + ["--offline"])
    settings = profile(java_version=25, java_home=str(jdk))
    bundle = NativeUnitBundle.model_validate(response_example(kind))
    files = validate_bundle(bundle, bundle.unit_contract.apis, bundle.unit_contract.requirements, bundle.evidence_ids)
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="prompt-example"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    with java_scope(settings):
        result, _ = accept_bundle(tmp_path / kind, files, context, settings, bundle.dependencies,
            required_tests={name for paths in bundle.coverage.values() for name in paths})
    assert result["build_passed"] and result["tests_passed"] and result["test_count"] > 0


@pytest.mark.parametrize("attempt", [1, 2, 3])
def test_latest_run_package_relative_paths_are_rejected_and_explicitly_guided(attempt):
    path = Path(__file__).parent / "fixtures/latest_prompt_path_responses.json"
    saved = json.loads(path.read_text(encoding="utf-8"))[attempt - 1]
    bundle = NativeUnitBundle.model_validate(saved["response"])
    with pytest.raises(ValueError, match="Native bundles contain only Java main/test sources"):
        validate_bundle(bundle)
    for instruction in (STEP, FORMAT):
        assert "Every file path starts with src/main/java/ or src/test/java/" in instruction
        assert "Never return package-relative paths" in instruction
