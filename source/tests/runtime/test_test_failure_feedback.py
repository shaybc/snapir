"""Verify structured test evidence, report capture and correction/Resume delivery."""

import json
import subprocess
import shutil
from pathlib import Path
from xml.etree import ElementTree
import pytest
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.test_feedback import test_correction as failure_correction, TestCorrectionError as FailureCorrectionError
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.resume_budget import with_resume_budget
from runtime.behavior_conversion.bundle_output import accept_bundle
from runtime.behavior_conversion.compatibility import _normalized
from tests.runtime.test_behavior_conversion import state, profile, factory


def failures():
    return json.loads((Path(__file__).parent / "fixtures/transfer_response_assertion_failures.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("index", [0, 1, 2])
def test_latest_failures_include_assertion_setup_and_implementation(index):
    saved = failures()[index]
    data = failure_correction(saved["error"], saved["response"]["files"])
    diagnostic = data["diagnostics"][0]
    assert diagnostic["line"] == 29
    assert diagnostic["expected_value"] == "true" and diagnostic["actual_value"] == "false"
    assert "<SourceAccount>  123</SourceAccount>" in diagnostic["source_line"]
    assert 'setSourceAccount("123")' in diagnostic["setup_and_assertion_context"]
    assert any('srcAcc.length() < 3' in item["content"] for item in data["relevant_implementation_sources"])
    assert any(item["path"].endswith("TransferFundsResponseXml.java") for item in data["relevant_implementation_sources"])
    assert data["original_test_output"] == saved["error"]


def report(project, category="failure"):
    saved = failures()[2]
    data = failure_correction(saved["error"], saved["response"]["files"])["diagnostics"][0]
    root = ElementTree.Element("testsuite", name=data["test_class"])
    case = ElementTree.SubElement(root, "testcase", classname=data["test_class"], name=data["test_method"])
    node = ElementTree.SubElement(case, category, message="expected: <true> but was: <false>", type="AssertionError")
    node.text = data["stack_trace"]
    ElementTree.SubElement(case, "system-out").text = "Observed test output"
    reports = Path(project) / "target/surefire-reports"
    reports.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(root).write(reports / "TEST-example.xml", encoding="utf-8")


@pytest.mark.parametrize("category, expected", [("failure", "assertion_failure"), ("error", "test_error")])
def test_report_capture_preserves_exception_and_output(tmp_path, category, expected):
    saved = failures()[2]
    report(tmp_path, category)
    data = failure_correction("Maven test failed", saved["response"]["files"], staged=tmp_path)
    diagnostic = data["diagnostics"][0]
    assert diagnostic["category"] == expected and diagnostic["exception_type"] == "AssertionError"
    assert diagnostic["report_file"] == "TEST-example.xml"
    assert diagnostic["test_output"] == "Observed test output"
    assert diagnostic["line"] == 29


def test_report_is_retained_before_temporary_candidate_disappears(tmp_path):
    saved = failures()[2]
    class Verifier:
        def __call__(self, dependency):
            pass
        def compile_project(self, project, allowed=(), *, goal="compile"):
            if goal == "test":
                report(project)
                return subprocess.CompletedProcess([], 1, saved["error"], "")
            return subprocess.CompletedProcess([], 0, "", "")
    with pytest.raises(FailureCorrectionError) as caught:
        accept_bundle(tmp_path / "candidate", {file["path"]: file["content"] for file in saved["response"]["files"]},
            factory(Verifier()), profile(), [])
    assert caught.value.test_correction["diagnostics"][0]["report_file"] == "TEST-example.xml"
    assert caught.value.test_correction["failed_sources"][0]["content"]
    assert not (tmp_path / "candidate").exists()


def test_failed_test_context_survives_correction_limit_and_explicit_resume():
    saved = failures()[2]
    conn, config = state()
    calls = []
    candidate = NativeUnitBundle.model_validate(saved["response"])
    context = failure_correction(saved["error"], saved["response"]["files"])
    def model(instruction, encoded):
        request = json.loads(encoded)
        calls.append(request)
        assert "test_correction" in instruction
        assert request["configuration_xml"] == saved["configuration_xml"]
        assert request["sources"] == saved["sources"]
        if len(calls) > 1:
            assert request["test_correction"]["failed_sources"] == context["failed_sources"]
            assert request["test_correction"]["diagnostics"][0]["source_line"] == context["diagnostics"][0]["source_line"]
            assert "previous_model_response" in request
        return candidate.model_dump_json()
    def validate(output, cached):
        raise FailureCorrectionError(saved["error"], context)
    @with_resume_budget
    def resume():
        return generate(conn, config, profile(), "unit", "format", "Convert", {"kind": "response_format",
            "configuration_xml": saved["configuration_xml"], "sources": saved["sources"]}, NativeUnitBundle,
            validator=validate, model_call=model)
    for _ in range(2):
        with pytest.raises(FailureCorrectionError):
            resume()
    assert len(calls) == 6
    stored = json.loads(conn.execute("select request_json from behavior_attempts order by attempt desc limit 1").fetchone()[0])
    assert stored["failed_test_context"]["diagnostics"]


def test_no_failure_is_invented_and_diagnostic_context_does_not_invalidate_reuse(tmp_path):
    assert failure_correction("No Maven errors", staged=tmp_path) is None
    assert _normalized({"kind": "step", "test_correction": {"x": 1}, "failed_test_context": {"y": 2}}) == {"kind": "step"}


def test_malformed_report_falls_back_to_retained_output_and_parameterized_frames(tmp_path):
    saved = failures()[2]
    report(tmp_path)
    path = tmp_path / "target/surefire-reports/TEST-example.xml"
    path.write_text("<broken", encoding="utf-8")
    data = failure_correction(saved["error"], saved["response"]["files"], staged=tmp_path)
    assert data["diagnostics"][0]["line"] == 29
    report(tmp_path)
    root = ElementTree.parse(path).getroot()
    case = root.find("testcase")
    case.set("name", "testFormatAndUnformat(String)[1]")
    failure = case.find("failure")
    failure.set("message", "Backend unavailable")
    failure.set("type", "java.io.IOException")
    root.remove(case)
    root.append(case)
    ElementTree.SubElement(root, "system-err").text = "Suite diagnostic"
    ElementTree.ElementTree(root).write(path, encoding="utf-8")
    diagnostic = failure_correction("Maven test failed", saved["response"]["files"], staged=tmp_path)["diagnostics"][0]
    assert diagnostic["line"] == 29
    assert "expected_value" not in diagnostic and "actual_value" not in diagnostic
    assert "Suite diagnostic" in diagnostic["test_output"]


def test_real_latest_failure_report_and_corrected_assertion_execute_on_java25(tmp_path):
    from types import SimpleNamespace
    from runtime.behavior_conversion.ownership import create_native_context
    from runtime.behavior_conversion.testing_contract import testing_contract as get_testing_contract
    from runtime.java_toolchain import java_scope
    from tools.maven_dependency_tools.build_context import ManagedBuildContext
    from tests.runtime.test_native_xml_build import OfflineVerifier
    jdk = Path("C:/Program Files/Java/jdk-25.0.3")
    if not shutil.which("mvn") or not jdk.is_dir():
        pytest.skip("Offline Maven/JDK unavailable")
    saved = failures()[2]
    candidate = NativeUnitBundle.model_validate(saved["response"])
    settings = profile(java_version=25, java_home=str(jdk))
    verifier = OfflineVerifier()
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="test-feedback-replay"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    def build(name):
        return accept_bundle(tmp_path / name, {file.path: file.content for file in candidate.files}, context, settings,
            candidate.dependencies, required_tests={name for paths in candidate.coverage.values() for name in paths},
            testing_contract=get_testing_contract(settings))
    with java_scope(settings):
        with pytest.raises(FailureCorrectionError) as caught:
            build("original")
        diagnostic = caught.value.test_correction["diagnostics"][0]
        assert diagnostic["expected_value"] == "true" and diagnostic["actual_value"] == "false"
        assert diagnostic["line"] == 29 and "<SourceAccount>  123" in diagnostic["source_line"]
        assert diagnostic["report_file"].startswith("TEST-")
        for file in candidate.files:
            if file.path.endswith("TransferFundsResponseMapperTest.java"):
                file.content = file.content.replace("<SourceAccount>  123</SourceAccount>", "<SourceAccount>123</SourceAccount>")
        result, _ = build("corrected")
    assert result["build_passed"] and result["tests_passed"] and result["test_count"] == 3
