"""Exercise managed runtime dispatch and build checkpoint invalidation."""

import json
import pytest
import subprocess

from models.pipeline_configuration import PipelineConfiguration
from runtime.managed_projects import enqueue_closure_conversions, run_managed_tasks
from tests.test_migration_planning import memory_conn, run_config, plan, batch, packet
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.maven_dependency_tools.build_invalidation import reconcile_pom_hash
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
from tools.state_store_tools.generated_artifacts import upsert_generated_artifact


def test_pom_change_invalidates_operation_build(tmp_path):
    conn = memory_conn()
    pom = tmp_path / "pom.xml"
    initialize_managed_pom(str(pom), "org.example", "service")
    upsert_generated_artifact(conn, artifact_id="service", run_id="run-1", operation_id="Op", channel="INTERNET",
                              target_language="java", artifact_kind="service", status="validated")
    assert not reconcile_pom_hash(conn, "run-1", str(pom), "Op", "INTERNET")
    pom.write_text(pom.read_text() + "\n")
    assert reconcile_pom_hash(conn, "run-1", str(pom), "Op", "INTERNET")
    assert conn.execute("SELECT status FROM generated_artifacts WHERE artifact_id='service'").fetchone()[0] == "needs_rerun"


@pytest.mark.parametrize("needs_correction", [False, True, "json", "schema", "exhausted"])
def test_ready_closure_dispatches_to_operation_pom(monkeypatch, tmp_path, needs_correction):
    conn = memory_conn()
    config = run_config().model_copy(update={"output_root": str(tmp_path / "generated")})
    original = tmp_path / "Step.java"
    original.write_text("public class Step {}")
    closure = dict(status="READY", operation_id="Op", channel="INTERNET", java_classes=[
        dict(fqcn="Step", source_file=str(original), shared=False)], formats={"all_format_ids": []})
    import hashlib
    closure.update(conversion_components_checked=True, conversion_components=[dict(kind="ibm_java", logical_id="Step",
        source_file=str(original), source_content=original.read_text(), source_hash=hashlib.sha256(original.read_bytes()).hexdigest())])
    closure.update(external_dependencies=[dict(class_name="vendor.Base", treatment="replace", behavior_description="Use context keys", behavior_evidence=[])],
                   composer_behavior_evidence=[dict(heading="Context", content="Read configured context keys", content_hash="evidence")])
    enqueue_closure_conversions(conn, config, [closure])
    enqueue_closure_conversions(conn, config, [closure])
    assert conn.execute("SELECT COUNT(*) FROM agent_tasks").fetchone()[0] == 1
    class Verifier:
        def __call__(self, proposal):
            pass
        def compile_project(self, root, allowed=(), *, goal="compile"):
            return subprocess.CompletedProcess(["mvn"], 0, "", "")
    def create(profile, project_root, artifact):
        pom = project_root / "pom.xml"
        initialize_managed_pom(str(pom), "org.example", artifact)
        return ManagedBuildContext(str(pom), Verifier())
    monkeypatch.setattr("runtime.managed_projects.create_build_context", create)
    calls = []
    def convert(self, instruction, payload):
        assert self.component_label == "Component 1/1: Step"
        request = json.loads(payload)
        calls.append(request)
        if needs_correction == "exhausted" or (needs_correction == "json" and len(calls) == 1):
            return '{"java_source": "broken",\\n "dependencies": []}'
        if needs_correction == "schema" and len(calls) == 1:
            return json.dumps({"java_source": "broken"})
        if needs_correction is True and len(calls) == 1:
            return json.dumps(dict(java_source="package com.company.generated; public class Step extends Base {}", dependencies=[]))
        assert request["external_dependencies"][0]["class_name"] == "vendor.Base"
        from runtime.composer_behavior_context import COMPOSER_SECTIONS
        assert tuple(item["heading"] for item in request["composer_behavior_evidence"]) == COMPOSER_SECTIONS
        assert all(item["content"] for item in request["composer_behavior_evidence"])
        assert "external_dependencies" in instruction
        return json.dumps(dict(java_source="package com.company.generated; public class Step {}", dependencies=[]))
    monkeypatch.setattr("runtime.managed_projects.AdkExecutor.execute", convert)
    profile = PipelineConfiguration(source_root=str(tmp_path), mapper_jar="mapper", output_root=str(tmp_path), channels=["INTERNET"])
    if needs_correction == "exhausted":
        with pytest.raises(ValueError, match="JSON parser"):
            run_managed_tasks(conn, config, profile, plan([batch("batch", [packet("Op")])]))
        assert len(calls) == profile.max_model_attempts
        assert conn.execute("SELECT status FROM agent_tasks").fetchone()[0] == "failed"
        assert not list((tmp_path / "generated").rglob("Step.java"))
        return
    results = run_managed_tasks(conn, config, profile, plan([batch("batch", [packet("Op")])]))
    assert results["compiled"] == 1
    assert len(calls) == (2 if needs_correction else 1)
    if needs_correction in ("json", "schema"):
        assert calls[-1]["response_correction_feedback"]
        assert calls[-1]["previous_model_response"]
    if needs_correction is True:
        assert "vendor.Base" in calls[-1]["replacement_correction_feedback"]
    assert (tmp_path / "generated/INTERNET/Op/src/main/java/com/company/generated/Step.java").is_file()
