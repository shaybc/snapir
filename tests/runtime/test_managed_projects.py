"""Exercise managed runtime dispatch and build checkpoint invalidation."""

import json
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


def test_ready_closure_dispatches_to_operation_pom(monkeypatch, tmp_path):
    conn = memory_conn()
    config = run_config().model_copy(update={"output_root": str(tmp_path / "generated")})
    original = tmp_path / "Step.java"
    original.write_text("public class Step {}")
    closure = dict(status="READY", operation_id="Op", channel="INTERNET", java_classes=[
        dict(fqcn="Step", source_file=str(original), shared=False)], formats={"all_format_ids": []})
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
    monkeypatch.setattr("runtime.managed_projects.AdkExecutor.execute", lambda self, instruction, payload:
                        json.dumps(dict(java_source="public class Step {}", dependencies=[])))
    profile = PipelineConfiguration(source_root=str(tmp_path), mapper_jar="mapper", output_root=str(tmp_path), channels=["INTERNET"])
    results = run_managed_tasks(conn, config, profile, plan([batch("batch", [packet("Op")])]))
    assert results["compiled"] == 1
    assert (tmp_path / "generated/INTERNET/Op/src/main/java/Step.java").is_file()
