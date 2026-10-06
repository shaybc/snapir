"""Verify component review, bounded correction, and evidence-bound Gate 2."""

import json

from models.pipeline_configuration import PipelineConfiguration
from runtime.component_review import run_component_review_gate
from runtime.human_gates import record_decision
from tests.test_migration_planning import memory_conn, run_config, plan, batch, packet
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom


def setup_run(tmp_path, policy="human", retries=2):
    conn = memory_conn()
    config = run_config().model_copy(update={"output_root": str(tmp_path / "generated")})
    profile = PipelineConfiguration(source_root=str(tmp_path), mapper_jar="mapper", output_root=str(tmp_path),
                                    channels=["INTERNET"], model_provider="mock", gate_policies={"2": policy})
    project = tmp_path / "generated/INTERNET/Op"
    source = project / "src/main/java/Step.java"
    source.parent.mkdir(parents=True)
    source.write_text("public class Step { public int execute() { return 0; } }")
    for folder in (project, tmp_path / "generated/common-lib"):
        initialize_managed_pom(str(folder / "pom.xml"), "org.example", folder.name)
    data = dict(conversion_id="Step", kind="ibm_java", channel="INTERNET",
                primary_source_content=source.read_text(), relationship_context="operation", target_kind="native_java",
                managed_project_operation="Op")
    upsert_agent_task(conn, task_id="component", run_id=config.run_id, agent_name="ManagedConversion",
                      scope_type="java_class", scope_id="Step", channel="INTERNET", target_language="java",
                      status="completed", input_data=data, max_retries=retries)
    upsert_native_java_artifact(conn, artifact_id="run-1:native_java:component", run_id=config.run_id,
                                conversion_id="Step", kind="ibm_java", logical_id="Step", artifact_path=str(source),
                                compiles=True, status="converted")
    return conn, config, profile, plan([batch("batch", [packet("Op")])]), source


def approved(item):
    return dict(conversion_id="Step", issues=[], confidence="high", review_status="approved")


def invoke(tmp_path, setup, reviewer=approved, **kwargs):
    conn, config, profile, migration_plan, _ = setup
    return run_component_review_gate(conn, config, profile, migration_plan, tmp_path,
                                      model_reviewer=reviewer, project_builder=lambda project: True, **kwargs)


def test_human_gate_requires_approval_and_reuses_unchanged_review(tmp_path):
    setup = setup_run(tmp_path)
    calls = []
    reviewer = lambda item: calls.append(item["original_source"]) or approved(item)
    assert invoke(tmp_path, setup, reviewer) == "gate_2_pending"
    record_decision(setup[0], "run-1", 2, (tmp_path / "gate_2_report.txt").read_text(), "approved")
    assert invoke(tmp_path, setup, reviewer) == "assembly_pending"
    assert len(calls) == 1


def test_changed_code_and_pom_require_new_review_and_approval(tmp_path):
    setup = setup_run(tmp_path)
    assert invoke(tmp_path, setup) == "gate_2_pending"
    record_decision(setup[0], "run-1", 2, (tmp_path / "gate_2_report.txt").read_text(), "approved")
    setup[-1].write_text(setup[-1].read_text() + "\n// changed")
    assert invoke(tmp_path, setup) == "gate_2_pending"
    record_decision(setup[0], "run-1", 2, (tmp_path / "gate_2_report.txt").read_text(), "approved")
    pom = setup[-1].parents[3] / "pom.xml"
    pom.write_text(pom.read_text() + "\n")
    assert invoke(tmp_path, setup) == "gate_2_pending"


def test_missing_component_blocks_skip_policy(tmp_path):
    setup = setup_run(tmp_path, "skip")
    setup[-1].unlink()
    assert invoke(tmp_path, setup) == "component_review_blocked"


def test_low_confidence_cannot_auto_approve(tmp_path):
    setup = setup_run(tmp_path, "automatic")
    assert invoke(tmp_path, setup, lambda item: dict(conversion_id="Step", issues=[], confidence="low", review_status="approved")) == "component_review_blocked"


def test_revision_limit_survives_resume(tmp_path):
    setup = setup_run(tmp_path, "automatic", retries=2)
    calls = []
    def reconvert():
        calls.append(True)
        setup[0].execute("UPDATE agent_tasks SET status='completed' WHERE task_id='component'")
        setup[0].commit()
        return {"failed": 0}
    reviewer = lambda item: dict(conversion_id="Step", issues=["Fix logic"], confidence="medium", review_status="needs_revision")
    assert invoke(tmp_path, setup, reviewer, conversion_runner=reconvert) == "component_review_blocked"
    assert len(calls) == 2
    assert invoke(tmp_path, setup, reviewer, conversion_runner=reconvert) == "component_review_blocked"
    assert len(calls) == 2


def test_successful_revision_passes_automatic_gate(tmp_path):
    setup = setup_run(tmp_path, "automatic")
    def reviewer(item):
        if "fixed" in item["converted_source"]:
            return approved(item)
        return dict(conversion_id="Step", issues=["Fix logic"], confidence="medium", review_status="needs_revision")
    def reconvert():
        setup[-1].write_text(setup[-1].read_text() + "\n// fixed")
        setup[0].execute("UPDATE agent_tasks SET status='completed' WHERE task_id='component'")
        setup[0].commit()
        return {"failed": 0}
    assert invoke(tmp_path, setup, reviewer, conversion_runner=reconvert) == "assembly_pending"


def test_unreviewed_source_blocks_automatic_gate(tmp_path):
    setup = setup_run(tmp_path, "automatic")
    setup[-1].with_name("Extra.java").write_text("public class Extra {}")
    assert invoke(tmp_path, setup) == "component_review_blocked"


def test_expected_missing_conversion_task_blocks_gate(tmp_path):
    setup = setup_run(tmp_path, "automatic")
    (tmp_path / "closures.json").write_text(json.dumps([dict(operation_id="Op", channel="INTERNET",
        java_classes=[dict(fqcn="Missing")], formats={"all_format_ids": []})]))
    assert invoke(tmp_path, setup) == "component_review_blocked"


def test_rejection_stays_effective(tmp_path):
    setup = setup_run(tmp_path)
    assert invoke(tmp_path, setup) == "gate_2_pending"
    record_decision(setup[0], "run-1", 2, (tmp_path / "gate_2_report.txt").read_text(), "rejected")
    assert invoke(tmp_path, setup) == "gate_2_rejected"


def test_component_build_excludes_registered_assembly_files(monkeypatch, tmp_path):
    setup = setup_run(tmp_path, "automatic")
    conn, config, profile, migration_plan, source = setup
    assembly = source.with_name("BrokenService.java")
    assembly.write_text("invalid assembly source")
    upsert_agent_task(conn, task_id="assembly", run_id=config.run_id, agent_name="ManagedAssembly",
                      scope_type="operation", scope_id="Op", channel="INTERNET", status="failed")
    upsert_native_java_artifact(conn, artifact_id="assembly-output", run_id=config.run_id,
                                conversion_id="Op", kind="xml_operation", logical_id="Op", artifact_path=str(assembly))
    paths = []
    class Verifier:
        def compile_project(self, project, allowed, *, goal):
            paths.append(project)
            assert not list(project.rglob("BrokenService.java"))
            if project.name == "Op":
                assert list(project.rglob("Step.java"))
            return type("Result", (), {"returncode": 0})()
    def context(profile, project, artifact):
        return type("Context", (), {"pom_path": str(project / "pom.xml"), "verifier": Verifier(), "allowed_ibm_artifacts": ()})()
    monkeypatch.setattr("runtime.managed_projects.create_build_context", context)
    assert run_component_review_gate(conn, config, profile, migration_plan, tmp_path,
                                     model_reviewer=approved) == "assembly_pending"
    assert paths and all(not path.exists() for path in paths)
