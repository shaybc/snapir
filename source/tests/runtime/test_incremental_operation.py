"""Compile-first assembly, scenario corrections and preservation of accepted tests."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.native_unit_bundle import NativeUnitBundle
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.incremental_operation import generate_incremental_operation
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.runner import _bundle_validator
from runtime.behavior_conversion.resume_budget import with_resume_budget
from runtime.behavior_conversion.bundle_output import validate_bundle, file_manifest
from runtime.behavior_conversion.bundle_output import accept_bundle
from runtime.behavior_conversion.compiler_feedback import CompilerCorrectionError
from runtime.behavior_conversion.testing_contract import attach_testing_contract
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.ownership import create_native_context
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.state_store_tools.behavior_units import snapshot
from tests.runtime.test_behavior_conversion import state, profile, factory, Verifier
from tests.runtime.test_native_xml_build import OfflineVerifier
from tests.runtime.test_operation_route_plan import saved_failure


def implementation():
    api = dict(type_name="com.company.generated.Flow", method_signatures=["public int execute(int input)"])
    unit = dict(unit_id="step", apis=[api], requirements={"business": "Choose a result"}, evidence_ids=["original"])
    return NativeUnitBundle(files=[dict(path="src/main/java/com/company/generated/Flow.java",
        content="package com.company.generated; public class Flow { public int execute(int input) { return input >= 0 ? 1 : -1; } }")],
        operation_contract=dict(sources=[{"identity": "original"}], units=[unit], service_api=api,
            request_type="int", success_type="int", error_type="int"))


def setup(tmp_path, context_factory=None):
    conn, config = state()
    project = tmp_path / "project"
    settings = profile(java_version=25, java_home="C:/Program Files/Java/jdk-25.0.3")
    requirements = {"route-entry": "Select successful or failed result", "operation-flow": "Execute configured flow"}
    payload = dict(operation_id="Flow", java_version=25, requirements=requirements,
        closure={"routing_graph": {"entry": {"on0Do": "end", "onOtherDo": "end"}}}, accepted_units={})
    attach_testing_contract(payload, settings)
    build = context_factory or factory(Verifier())
    provisional = _bundle_validator(conn, config, settings, project, "service_implementation:WEB/Flow", (), (), (), build, require_tests=False)
    def final(bundle, cached=False, excluded_tests=()):
        return _bundle_validator(conn, config, settings, project, "service:WEB/Flow", (), requirements, (), build,
            excluded_test_files=excluded_tests, remove_excluded_tests=True)(bundle, cached=cached)
    scenarios = lambda identity, covers, excluded_tests=(): _bundle_validator(conn, config, settings, project,
        "route_scenario:" + identity, (), covers, (), build, excluded_test_files=excluded_tests)
    return conn, config, settings, payload, provisional, final, scenarios, project


class Model:
    def __init__(self, fail_second=False, scale=1, failure_id="failure"):
        self.requests, self.fail_second = [], fail_second
        self.scale, self.failure_id = scale, failure_id

    def __call__(self, instruction, encoded):
        request = json.loads(encoded)
        self.requests.append(request)
        phase = request["assembly_phase"]
        if phase == "implementation_compile":
            assert "main files only" in instruction
            assert "coverage_owner" in request
            candidate = implementation()
            candidate.files[0].content = candidate.files[0].content.replace("? 1 : -1", "? " + str(self.scale) + " : -" + str(self.scale))
            return candidate.model_dump_json()
        if phase == "route_test_plan":
            assert request["assembled_code"] and request["closure"]["routing_graph"]
            return json.dumps(dict(scenarios=[dict(scenario_id=name, description="Execute " + name,
                inputs=["input=" + str(value)], dependency_setup=[], expected_outcome="result=" + str(result),
                covers=list(request["requirements"]), routes=[dict(source="entry", outcome=outcome, target="end")])
                for name, value, result, outcome in [("success", 1, self.scale, "on0Do"), (self.failure_id, -1, -self.scale, "onOtherDo")]]))
        assert phase == "single_route_test" and "one focused operation test" in instruction
        scenario = request["scenario"]
        value, result = (1, self.scale) if scenario["scenario_id"] == "success" else (-1, -self.scale)
        content = ("package " + request["test_package"] + "; public class " + request["test_class"] + " { " +
            "@org.junit.jupiter.api.Test public void executesExpectedBranch() { org.junit.jupiter.api.Assertions.assertEquals(" +
            str(result) + ", new com.company.generated.Flow().execute(" + str(value) + ")); } }")
        if self.fail_second and scenario["scenario_id"] == "failure":
            return json.dumps({"files": [{"path": "src/main/java/com/company/generated/Flow.java", "content": content}]})
        return NativeUnitBundle(files=[dict(path=request["expected_test_path"], content=content)]).model_dump_json()


def invoke(tmp_path, values, model):
    conn, config, settings, payload, provisional, final, scenarios, project = values
    return generate_incremental_operation(conn, config, settings, "WEB/Flow", payload, final, provisional, scenarios,
        tmp_path / "run", model)


def test_compile_plan_scenarios_final_suite_and_full_reuse(tmp_path):
    values = setup(tmp_path)
    model = Model()
    bundle, fingerprint = invoke(tmp_path, values, model)
    assert [request["assembly_phase"] for request in model.requests] == ["implementation_compile", "route_test_plan", "single_route_test", "single_route_test"]
    assert len(bundle.coverage["route-entry"]) == 2 and len(bundle.files) == 3
    assert all(request["scenario"]["scenario_id"] in ("success", "failure") for request in model.requests[2:])
    conn = values[0]
    assert snapshot(conn, "pilot", "service", "WEB/Flow")["status"] == "accepted"
    count = len(model.requests)
    before = file_manifest(values[-1], [file.path for file in bundle.files])
    result, reused = invoke(tmp_path, values, model)
    assert len(model.requests) == count and reused == fingerprint
    assert file_manifest(values[-1], before) == before
    assert result.coverage == bundle.coverage


def test_failed_scenario_resume_keeps_accepted_test_and_implementation(tmp_path):
    values = setup(tmp_path)
    model = Model(fail_second=True)
    resume = with_resume_budget(lambda: invoke(tmp_path, values, model))
    with pytest.raises(ValueError, match="assigned test file"):
        resume()
    conn = values[0]
    assert snapshot(conn, "pilot", "service", "WEB/Flow") is None
    assert snapshot(conn, "pilot", "route_scenario_test", "WEB/Flow:success")["status"] == "accepted"
    success_file = model.requests[2]["expected_test_path"]
    before = file_manifest(values[-1], [success_file, implementation().files[0].path])
    count = len(model.requests)
    model.fail_second = False
    result, _ = resume()
    assert len(model.requests) == count + 1
    assert model.requests[-1]["scenario"]["scenario_id"] == "failure"
    assert "correction_feedback" in model.requests[-1]
    assert file_manifest(values[-1], before) == before
    assert len(result.coverage["operation-flow"]) == 2


def test_compilation_failure_prevents_planning_and_test_requests(tmp_path):
    values = setup(tmp_path, factory(Verifier(failing=True)))
    model = Model()
    with pytest.raises(ValueError, match="Maven compile"):
        invoke(tmp_path, values, model)
    assert all(request["assembly_phase"] == "implementation_compile" for request in model.requests)
    assert snapshot(values[0], "pilot", "route_test_plan", "WEB/Flow") is None


def test_latest_empty_coverage_response_is_provisional_not_a_complete_acceptance(tmp_path):
    saved = saved_failure()
    candidate = NativeUnitBundle.model_validate(saved["response"])
    candidate.files = [file for file in candidate.files if file.path.startswith("src/main/java/")]
    assert candidate.coverage == {}
    conn, config = state()
    verified = []
    def validate(output, cached):
        validate_bundle(output, [output.operation_contract.service_api], ())
        verified.append(output)
    result, _ = generate(conn, config, profile(), "service_implementation", "operation", "Implementation only",
        {"requirements": saved["requirements"], "kind": "service"}, NativeUnitBundle, validate,
        model_call=lambda *_: candidate.model_dump_json(), require_coverage=False)
    assert verified and result.coverage == {}
    assert snapshot(conn, "pilot", "service", "operation") is None


def test_changed_implementation_excludes_stale_tests_until_replacements_pass(tmp_path):
    class CheckingVerifier(Verifier):
        changed = False
        def compile_project(self, project, allowed=(), *, goal="compile"):
            if goal == "test" and self.changed:
                for path in (Path(project) / "src/test/java").rglob("Route*Test.java"):
                    text = path.read_text(encoding="utf-8")
                    assert "assertEquals(1," not in text and "assertEquals(-1," not in text
            return super().compile_project(project, allowed, goal=goal)
    verifier = CheckingVerifier()
    values = setup(tmp_path, factory(verifier))
    first, _ = invoke(tmp_path, values, Model())
    old = file_manifest(values[-1], [file.path for file in first.files])
    values[3]["closure"]["ini_values"] = {"scale": 2}
    verifier.changed = True
    second, _ = invoke(tmp_path, values, Model(scale=2))
    assert "? 2 : -2" in second.files[0].content
    assert old != file_manifest(values[-1], [file.path for file in second.files])
    assert snapshot(values[0], "pilot", "service", "WEB/Flow")["status"] == "accepted"


def test_removed_scenario_file_is_retired_only_after_final_success(tmp_path):
    values = setup(tmp_path)
    first, _ = invoke(tmp_path, values, Model())
    old_path = first.coverage["route-entry"][1]
    values[3]["closure"]["ini_values"] = {"new_revision": True}
    replacement = Model(fail_second=True, failure_id="replacement")
    # Change only the assigned failing ID in this fixture's rejection behavior.
    original = replacement.__class__.__call__
    class FailingReplacement(Model):
        def __call__(self, instruction, encoded):
            data = json.loads(encoded)
            if data.get("scenario", {}).get("scenario_id") == "replacement":
                self.requests.append(data)
                return json.dumps({"files": [{"path": "invalid", "content": "invalid"}]})
            return original(self, instruction, encoded)
    resume = with_resume_budget(lambda model: invoke(tmp_path, values, model))
    with pytest.raises(ValueError):
        resume(FailingReplacement(failure_id="replacement"))
    assert (values[-1] / old_path).is_file()
    final, _ = resume(Model(failure_id="replacement"))
    assert not (values[-1] / old_path).exists()
    assert old_path not in {file.path for file in final.files}
    assert snapshot(values[0], "pilot", "route_scenario_test", "WEB/Flow:failure")["status"] == "retired"


def test_user_changed_accepted_test_is_not_overwritten_on_resume(tmp_path):
    values = setup(tmp_path)
    first, _ = invoke(tmp_path, values, Model())
    path = values[-1] / first.coverage["route-entry"][0]
    path.write_text("User changed this file", encoding="utf-8")
    with pytest.raises(ValueError, match="Accepted native source changed"):
        invoke(tmp_path, values, Model())
    assert path.read_text() == "User changed this file"


def test_real_java25_compiles_first_then_executes_each_scenario_and_full_suite(tmp_path):
    if not shutil.which("mvn") or not Path("C:/Program Files/Java/jdk-25.0.3").is_dir():
        pytest.skip("Offline Maven/JDK unavailable")
    verifier = OfflineVerifier()
    calls = []
    def context(settings, project, artifact):
        parent = SimpleNamespace(run_id="incremental-operation-real")
        result = create_native_context(parent, settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
        class TracedVerifier:
            def __call__(self, dependency):
                return verifier(dependency)
            def compile_project(self, project, allowed=(), *, goal="compile"):
                calls.append(goal)
                return verifier.compile_project(project, allowed, goal=goal)
        result.verifier = TracedVerifier()
        return result
    values = setup(tmp_path, context)
    with java_scope(values[2]):
        bundle, _ = invoke(tmp_path, values, Model())
    assert calls == ["compile", "compile", "test", "compile", "test", "compile", "test"]
    result = json.loads(snapshot(values[0], "pilot", "manifest", "service:WEB/Flow")["data_json"])["validation"]
    assert result["tests_passed"] and result["test_count"] == 2
    assert len(bundle.coverage["route-entry"]) == 2


def test_real_latest_assembly_response_is_checked_for_compilation_before_route_tests(tmp_path):
    if not shutil.which("mvn") or not Path("C:/Program Files/Java/jdk-25.0.3").is_dir():
        pytest.skip("Offline Maven/JDK unavailable")
    saved = saved_failure()
    candidate = NativeUnitBundle.model_validate(saved["response"])
    files = {file["path"]: file["content"] for file in saved["accepted_unit_sources"]}
    files.update({file.path: file.content for file in candidate.files if file.path.startswith("src/main/java/")})
    settings = profile(java_version=25, java_home="C:/Program Files/Java/jdk-25.0.3")
    verifier = OfflineVerifier()
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="latest-assembly-replay"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    with java_scope(settings):
        with pytest.raises(CompilerCorrectionError) as caught:
            accept_bundle(tmp_path / "latest", files, context, settings,
                [MavenDependency.model_validate(item) for item in saved["known_dependencies"]], require_tests=False)
    assert "Missing test coverage" not in str(caught.value)
    assert any(item["file"].endswith("TransferFundsOp.java") for item in caught.value.compiler_correction["diagnostics"])
