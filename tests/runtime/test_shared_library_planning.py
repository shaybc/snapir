"""Check reviewed library grouping and source-based conversion reuse."""

import json
import subprocess
from pathlib import Path

from models.pipeline_configuration import PipelineConfiguration
from runtime.managed_projects import enqueue_closure_conversions, run_managed_tasks
from runtime.shared_libraries.registry import register_approved_components, reusable_component
from runtime.component_review.evidence import collect_component_evidence
from tools.component_inventory_tools.library_planner import prepare_library_plan
from tools.component_inventory_tools import build_component_inventory
from tools.state_store_tools.component_inventory import persist_component_inventory
from tests.test_component_inventory import make_workspace
from tests.test_migration_planning import memory_conn, run_config, plan, batch, packet
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact


def setup(tmp_path, threshold=20):
    workspace, java = make_workspace(tmp_path)
    conn = memory_conn()
    config = run_config().model_copy(update=dict(source_root=str(workspace), output_root=str(tmp_path / "generated")))
    profile = PipelineConfiguration(source_root=str(workspace), mapper_jar="mapper", output_root=str(tmp_path),
        channels=["WEB", "KIOSK"], shared_library_min_usage=1 if threshold == 2 else 2,
        broad_library_usage_threshold=threshold - 1)
    inventory = build_component_inventory(workspace, "enterprise")
    persist_component_inventory(conn, config.run_id, inventory)
    first = packet("WebOp").model_copy(update=dict(channel="WEB"))
    second = packet("KioskOp").model_copy(update=dict(channel="KIOSK"))
    migration = plan([batch("batch", [first, second])])
    libraries = prepare_library_plan(conn, config, profile, migration)
    closures = [dict(status="READY", operation_id=operation, channel=channel,
        java_classes=[dict(fqcn="org.example.CheckDatabase", source_file=str(java), shared=False)],
        formats={"all_format_ids": []}) for operation, channel in (("WebOp", "WEB"), ("KioskOp", "KIOSK"))]
    return conn, config, profile, migration, libraries, closures


def test_small_consumer_set_gets_grouped_library_and_one_cross_channel_task(tmp_path):
    conn, config, profile, migration, libraries, closures = setup(tmp_path)
    assert any(library.library_id.startswith("shared-") for library in libraries.libraries)
    enqueue_closure_conversions(conn, config, closures)
    rows = conn.execute("SELECT input_json FROM agent_tasks WHERE scope_id='org.example.CheckDatabase'").fetchall()
    assert len(rows) == 1
    data = json.loads(rows[0][0])
    assert data["managed_library_id"].startswith("shared-")
    assert set(data["consumer_operations"]) == {"WEB/WebOp", "KIOSK/KioskOp"}


def test_broad_sharing_threshold_assigns_common_library(tmp_path):
    _, _, _, _, libraries, _ = setup(tmp_path, threshold=2)
    assert any(library.library_id == "common-lib" for library in libraries.libraries)


def test_changed_source_blocks_stale_inventory_binding(tmp_path):
    conn, config, _, _, _, closures = setup(tmp_path)
    Path(closures[0]["java_classes"][0]["source_file"]).write_text("changed")
    import pytest
    with pytest.raises(ValueError, match="changed after inventory"):
        enqueue_closure_conversions(conn, config, closures)


class Verifier:
    def __call__(self, proposal):
        pass

    def compile_project(self, root, allowed=(), *, goal="compile"):
        return subprocess.CompletedProcess([], 0, "", "")


def factory(profile, project, artifact):
    pom = project / "pom.xml"
    initialize_managed_pom(str(pom), "org.example", artifact)
    return ManagedBuildContext(str(pom), Verifier())


def test_planned_library_builds_and_reviewed_registry_skips_model(monkeypatch, tmp_path):
    conn, config, profile, migration, _, closures = setup(tmp_path)
    enqueue_closure_conversions(conn, config, closures)
    # Restrict this fixture to one source component; formatter behavior has separate tests.
    conn.execute("DELETE FROM agent_tasks WHERE scope_id<>'org.example.CheckDatabase'")
    conn.commit()
    monkeypatch.setattr("runtime.managed_projects.create_build_context", factory)
    calls = []
    monkeypatch.setattr("runtime.managed_projects.AdkExecutor.execute", lambda self, instruction, payload:
        calls.append(payload) or json.dumps(dict(java_source="package org.example; public class CheckDatabase {}", dependencies=[])))
    assert run_managed_tasks(conn, config, profile, migration)["compiled"] == 1
    evidence = collect_component_evidence(conn, config, profile)
    assert not evidence[0]["issues"]
    assert Path(evidence[0]["project"]).parent.name == "libraries"
    # This fixture models the accepted Gate 2 publication boundary.
    register_approved_components(conn, config, profile, evidence)
    context = factory(profile, Path(evidence[0]["project"]), Path(evidence[0]["project"]).name)
    assert reusable_component(conn, config, profile, evidence[0]["task_input"], context) is not None
    conn.execute("UPDATE agent_tasks SET status='needs_rerun' WHERE scope_id='org.example.CheckDatabase'")
    conn.commit()
    result = run_managed_tasks(conn, config, profile, migration)
    assert result["reused"] == 1
    assert len(calls) == 1
    source = Path(evidence[0]["source_path"])
    source.write_text(source.read_text() + "// modified")
    data = evidence[0]["task_input"]
    context = factory(profile, Path(evidence[0]["project"]), Path(evidence[0]["project"]).name)
    assert reusable_component(conn, config, profile, data, context) is None


def test_configurable_usage_threshold_boundaries(tmp_path):
    import pytest
    for count, expected in ((4, "local"), (5, "small"), (10, "small"), (11, "broad")):
        root = tmp_path / str(count)
        root.mkdir()
        conn, config, profile, migration, _, closures = setup(root)
        profile.shared_library_min_usage = 5
        profile.broad_library_usage_threshold = 10
        xml = Path(config.source_root) / "Web/src/Channel/WEB/operation.xml"
        extra = ''.join(f'<opStep id="Additional{index}" implClass="org.example.CheckDatabase"/>' for index in range(count - 2))
        xml.write_text(xml.read_text().replace("<refFormat", extra + "<refFormat"))
        persist_component_inventory(conn, config.run_id, build_component_inventory(config.source_root, "enterprise"))
        library_plan = prepare_library_plan(conn, config, profile, migration)
        row = next(json.loads(row[0]) for row in conn.execute("SELECT record_json FROM source_implementations")
                   if json.loads(row[0])["class_name"] == "CheckDatabase")
        library = library_plan.assignments["implementation:" + row["implementation_id"]]
        assert (library is None) if expected == "local" else library == "common-lib" if expected == "broad" else library.startswith("shared-")
        enqueue_closure_conversions(conn, config, closures)
        tasks = conn.execute("SELECT input_json FROM agent_tasks WHERE scope_id='org.example.CheckDatabase'").fetchall()
        assert len(tasks) == (2 if expected == "local" else 1)


def test_invalid_threshold_order_is_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="at least"):
        PipelineConfiguration(source_root=str(tmp_path), mapper_jar="mapper", output_root=str(tmp_path), channels=["WEB"],
                              shared_library_min_usage=12, broad_library_usage_threshold=10)
