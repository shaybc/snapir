"""Check protected service generation, durable retries and missing evidence."""

import subprocess
from pathlib import Path

from runtime.service_generation import run_service_generation
from runtime.service_generation.validation import validate_service_project
from tests.runtime.test_operation_review_gate import setup_review, invoke
from tools.maven_dependency_tools.build_context import ManagedBuildContext


def wrappers(payload):
    return dict(dependencies=[], files={
        "src/main/java/org/example/Application.java": "@SpringBootApplication class Application {}",
        "src/main/java/org/example/controller/OpController.java": "@RestController class OpController {}",
        "src/main/java/org/example/xml/JaxbConfig.java": "class JaxbConfig {}",
        "src/main/java/org/example/error/GlobalExceptionHandler.java": "class GlobalExceptionHandler {}",
        "src/main/resources/application.properties": "server.port=8080",
    })


class Verifier:
    def __call__(self, dependency):
        pass

    def compile_project(self, project, allowed=(), *, goal="compile"):
        return subprocess.CompletedProcess([], 0, "", "")


def ready(tmp_path):
    setup, gate, assemble = setup_review(tmp_path, "automatic")
    from constants import COMMON_LIB_GROUP_ID, COMMON_LIB_ARTIFACT_ID
    from models.maven_dependency import MavenDependency
    from tools.maven_dependency_tools.pom_manager import merge_dependencies
    import hashlib
    pom = Path(setup[1].output_root) / "INTERNET/Op/pom.xml"
    merge_dependencies(str(pom), [MavenDependency(group_id=COMMON_LIB_GROUP_ID,
        artifact_id=COMMON_LIB_ARTIFACT_ID, version="1.0.0", reason="Fixture shared module")], lambda value: None)
    setup[0].execute("UPDATE operation_assembly_snapshots SET pom_hash=?", (hashlib.sha256(pom.read_bytes()).hexdigest(),))
    setup[0].commit()
    assert invoke(tmp_path, setup, gate, assemble) == "service_generation_pending"
    return setup


def run(tmp_path, setup, generator=wrappers, validator=None, gate=None):
    conn, config, profile, plan, _ = setup
    return run_service_generation(conn, config, profile, plan, tmp_path,
        gate_checker=gate or (lambda: "service_generation_pending"), generator=generator,
        context_factory=lambda profile, project, artifact: ManagedBuildContext(str(project / "pom.xml"), Verifier()),
        validator=validator or (lambda project, context: dict(build_passed=True, package_passed=True,
            ibm_guard_passed=True, test_status="passed", behavioral_equivalence="not_available")))


def test_generation_preserves_sources_and_reuses_unchanged_success(tmp_path):
    setup = ready(tmp_path)
    calls = []
    generator = lambda payload: calls.append(True) or wrappers(payload)
    assert run(tmp_path, setup, generator) == "validation_evidence_pending"
    assert run(tmp_path, setup, generator) == "validation_evidence_pending"
    assert len(calls) == 1
    source = Path(setup[1].output_root) / "INTERNET/Op/src/main/java/org/example/OpService.java"
    assert source.read_bytes() == (tmp_path / "services/INTERNET/Op/src/main/java/org/example/OpService.java").read_bytes()


def test_changed_approved_source_is_rejected(tmp_path):
    setup = ready(tmp_path)
    def bad(payload):
        output = wrappers(payload)
        output["files"][next(iter(payload["approved_sources"]))] = "changed"
        return output
    assert run(tmp_path, setup, bad) == "service_generation_blocked"


def test_failed_generation_retry_budget_survives_resume(tmp_path):
    setup = ready(tmp_path)
    setup[1].max_agent_task_retries = 1
    calls = []
    bad = lambda payload: calls.append(True) or dict(files={"../bad": "x"}, dependencies=[])
    assert run(tmp_path, setup, bad) == "service_generation_blocked"
    assert run(tmp_path, setup, bad) == "service_generation_blocked"
    assert len(calls) == 1


def test_operation_dependency_pin_retries_only_wrapper_and_verifies_selected_version(tmp_path):
    """A corrected driver choice changes generation identity without altering approved code."""
    from models.maven_dependency import MavenDependency
    from runtime.service_generation.runner import generation_settings_identity
    from runtime.service_generation.dependency_pins import operation_dependency_pins
    setup = ready(tmp_path)
    setup[1].max_agent_task_retries = 1
    assert run(tmp_path, setup, lambda payload: dict(files={"../bad": "x"}, dependencies=[])) == "service_generation_blocked"
    before = generation_settings_identity(setup[2])
    pin = MavenDependency(group_id="example.jdbc", artifact_id="driver", version="1.2.3",
        reason="Verified deployment driver", required_classes=["example.Driver"])
    setup[2].service_maven_dependencies = {"INTERNET/Op": [pin]}
    assert generation_settings_identity(setup[2]) != before
    assert operation_dependency_pins(setup[2], "OTHER", "Op") == []
    checked, requests = [], []
    class PinnedVerifier(Verifier):
        def __call__(self, dependency):
            checked.append(dependency.model_copy(deep=True))
            assert dependency.version == "1.2.3"
    def generator(payload):
        requests.append(payload)
        result = wrappers(payload)
        result["dependencies"] = [pin.model_copy(update={"version": "9.9.9", "required_classes": ["example.Extra"]}).model_dump()]
        return result
    assert run_service_generation(setup[0], setup[1], setup[2], setup[3], tmp_path,
        gate_checker=lambda: "service_generation_pending", generator=generator,
        context_factory=lambda profile, project, artifact: ManagedBuildContext(str(project / "pom.xml"), PinnedVerifier()),
        validator=lambda project, context: dict(build_passed=True, package_passed=True, ibm_guard_passed=True, test_status="passed")) == "validation_evidence_pending"
    assert requests[0]["pinned_dependencies"] == [pin.model_dump()]
    assert checked and set(checked[0].required_classes) == {"example.Driver", "example.Extra"}
    assert pin.required_classes == ["example.Driver"]
    source = Path(setup[1].output_root) / "INTERNET/Op/src/main/java/org/example/OpService.java"
    assert source.read_bytes() == (tmp_path / "services/INTERNET/Op/src/main/java/org/example/OpService.java").read_bytes()


def test_generated_pom_feedback_names_file_and_keeps_managed_build(tmp_path):
    """The correction receives the rejected path instead of repeating a generated POM."""
    setup = ready(tmp_path)
    requests = []
    def generator(payload):
        requests.append(payload)
        output = wrappers(payload)
        if len(requests) == 1:
            output["files"]["pom.xml"] = "untrusted generated build"
        else:
            assert "remove pom.xml from files" in payload["validation_feedback"]["error"]
            assert "dependency proposals in dependencies" in payload["validation_feedback"]["error"]
        return output
    assert run(tmp_path, setup, generator) == "validation_evidence_pending"
    assert len(requests) == 2
    assert "untrusted generated build" not in (tmp_path / "services/INTERNET/Op/pom.xml").read_text()


def test_unapproved_gate_prevents_generation(tmp_path):
    setup = ready(tmp_path)
    assert run(tmp_path, setup, gate=lambda: "gate_3_pending") == "operation_gate_not_accepted"
    assert not (tmp_path / "services").exists()


def test_no_test_reports_are_not_a_validation_pass(tmp_path):
    context = ManagedBuildContext(str(tmp_path / "pom.xml"), Verifier())
    result = validate_service_project(tmp_path, context)
    assert result["build_passed"]
    assert result["test_status"] == "not_available"
    assert result["behavioral_equivalence"] == "not_available"


def test_mutated_final_project_is_regenerated(tmp_path):
    setup = ready(tmp_path)
    calls = []
    generator = lambda payload: calls.append(True) or wrappers(payload)
    assert run(tmp_path, setup, generator) == "validation_evidence_pending"
    (tmp_path / "services/INTERNET/Op/src/main/resources/application.properties").write_text("changed")
    assert run(tmp_path, setup, generator) == "validation_evidence_pending"
    assert len(calls) == 2


def test_build_failure_retries_with_saved_feedback(tmp_path):
    setup = ready(tmp_path)
    requests = []
    def generator(payload):
        requests.append(payload)
        return wrappers(payload)
    validations = []
    def validator(project, context):
        validations.append(True)
        if len(validations) == 1:
            return dict(build_passed=False, failure_class="build_failure", compile_log={"stderr": "missing API"})
        return dict(build_passed=True, package_passed=True, ibm_guard_passed=True, test_status="passed")
    assert run(tmp_path, setup, generator, validator) == "validation_evidence_pending"
    assert len(requests) == 2
    assert requests[1]["validation_feedback"]["compile_log"]["stderr"] == "missing API"
    assert requests[1]["previous_generation"] == wrappers({})


def test_missing_evidence_does_not_trigger_generation_loop(tmp_path):
    setup = ready(tmp_path)
    requests = []
    generator = lambda payload: requests.append(payload) or wrappers(payload)
    validator = lambda project, context: dict(build_passed=True, package_passed=True, ibm_guard_passed=True,
                                              test_status="not_available")
    assert run(tmp_path, setup, generator, validator) == "service_generation_blocked"
    assert run(tmp_path, setup, generator, validator) == "service_generation_blocked"
    assert len(requests) == 1


def test_routing_failure_queues_assembly_and_persists_budget(tmp_path):
    from runtime.service_generation.corrections import route_correction
    from runtime.operation_review.evidence import collect_operation_evidence
    setup = ready(tmp_path)
    conn, config, profile, plan, _ = setup
    config.max_agent_task_retries = 1
    item = collect_operation_evidence(conn, config, profile, plan)[0]
    result = dict(failure_class="routing_mismatch", findings=["RC branch missing"])
    assert route_correction(conn, config, item, result) == "assembly"
    assert conn.execute("SELECT status FROM agent_tasks WHERE task_id=?", (item["assembly_task_id"],)).fetchone()[0] == "needs_rerun"
    assert route_correction(conn, config, item, result) == "exhausted"


def test_component_correction_requires_explicit_owned_task(tmp_path):
    from runtime.service_generation.corrections import route_correction
    from runtime.operation_review.evidence import collect_operation_evidence
    setup = ready(tmp_path)
    conn, config, profile, plan, _ = setup
    item = collect_operation_evidence(conn, config, profile, plan)[0]
    assert route_correction(conn, config, item, dict(failure_class="conversion_gap")) == "human"
    assert route_correction(conn, config, item, dict(failure_class="conversion_gap", component_task_ids=["unknown"])) == "human"
    assert route_correction(conn, config, item, dict(failure_class="conversion_gap", component_task_ids=["reply"],
                                                  findings=["Field missing"])) == "component"
    row = conn.execute("SELECT status,input_json FROM agent_tasks WHERE task_id='reply'").fetchone()
    assert row[0] == "pending"
    import json
    assert json.loads(row[1])["component_review_feedback"] == ["Field missing"]
