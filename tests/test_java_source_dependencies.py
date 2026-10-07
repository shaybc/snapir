"""Verify Java-derived utility consumers, ownership, scheduling and invalidation."""

import json
from pathlib import Path

import pytest

from tools.component_inventory_tools import build_component_inventory
from tools.component_inventory_tools.library_planner import prepare_library_plan
from tools.state_store_tools.component_inventory import persist_component_inventory, get_implementation_usage
from tests.runtime.test_shared_library_planning import setup, factory
from runtime.managed_projects import enqueue_closure_conversions, run_managed_tasks
from runtime.shared_libraries.dependencies import ordered_conversion_tasks
from runtime.component_review.evidence import collect_component_evidence


def with_utilities(tmp_path, calls=1):
    conn, config, profile, migration, _, closures = setup(tmp_path)
    source = Path(closures[0]["java_classes"][0]["source_file"])
    expression = " + ".join("Helper.value()" for _ in range(calls))
    source.write_text("package org.example; import org.example.Helper; public class CheckDatabase { "
                      "public boolean available() { return (" + expression + ") > 0; } }")
    common = Path(config.source_root) / "Common/src/org/example"
    helper = common / "Helper.java"
    helper.write_text("package org.example; public class Helper { public static int value() { return Leaf.value(); } }")
    leaf = common / "Leaf.java"
    leaf.write_text("package org.example; public class Leaf { public static int value() { return 1; } }")
    inventory = build_component_inventory(config.source_root, "enterprise")
    persist_component_inventory(conn, config.run_id, inventory)
    libraries = prepare_library_plan(conn, config, profile, migration)
    return conn, config, profile, migration, closures, inventory, libraries, helper, leaf


def identities(inventory):
    return {item.class_name: item.implementation_id for item in inventory.implementations}


def test_transitive_utility_consumers_are_persisted_and_counted(tmp_path):
    conn, config, _, _, _, inventory, _, _, _ = with_utilities(tmp_path, calls=3)
    ids = identities(inventory)
    pairs = {(edge.caller_implementation_id, edge.target_implementation_id) for edge in inventory.java_dependencies.dependencies}
    assert (ids["CheckDatabase"], ids["Helper"]) in pairs
    assert (ids["Helper"], ids["Leaf"]) in pairs
    summaries = {item["implementation"]["class_name"]: item for item in get_implementation_usage(conn, config.run_id)}
    assert summaries["Helper"]["operation_count"] == 2
    assert summaries["Helper"]["channel_count"] == 2
    assert summaries["Helper"]["direct_reference_count"] == 0
    assert summaries["Helper"]["indirect_reference_count"] == 6
    assert summaries["Leaf"]["indirect_reference_count"] == 6


def test_unused_imports_comments_and_strings_do_not_create_utility_edges(tmp_path):
    _, config, _, _, closures, _, _, _, _ = with_utilities(tmp_path)
    source = Path(closures[0]["java_classes"][0]["source_file"])
    source.write_text('package org.example; import org.example.Helper; import static org.example.Leaf.*; '
                      'public class CheckDatabase { /* Helper.value() */ public String text() { return "Leaf.value()"; } }')
    inventory = build_component_inventory(config.source_root, "enterprise")
    root = identities(inventory)["CheckDatabase"]
    assert not [edge for edge in inventory.java_dependencies.dependencies if edge.caller_implementation_id == root]


@pytest.mark.parametrize("body", [
    "return org.example.Helper.value() > 0;",
    "Helper helper = new Helper(); return helper.value() > 0;",
    "java.util.List<Helper> helpers = null; return true;",
])
def test_fully_qualified_same_package_and_declared_types_resolve(tmp_path, body):
    _, config, _, _, closures, _, _, _, _ = with_utilities(tmp_path)
    source = Path(closures[0]["java_classes"][0]["source_file"])
    source.write_text("package org.example; public class CheckDatabase { public boolean available() { " + body + " } }")
    inventory = build_component_inventory(config.source_root, "enterprise")
    ids = identities(inventory)
    assert any(edge.caller_implementation_id == ids["CheckDatabase"] and edge.target_implementation_id == ids["Helper"]
               for edge in inventory.java_dependencies.dependencies)


def test_static_import_calls_resolve_without_scheduling_unused_imports(tmp_path):
    _, config, _, _, closures, _, _, _, _ = with_utilities(tmp_path)
    source = Path(closures[0]["java_classes"][0]["source_file"])
    source.write_text("package org.example; import static org.example.Helper.value; public class CheckDatabase { public boolean available() { return value() > 0; } }")
    inventory = build_component_inventory(config.source_root, "enterprise")
    ids = identities(inventory)
    assert any(edge.target_implementation_id == ids["Helper"] and edge.reference_kind == "static_member"
               for edge in inventory.java_dependencies.dependencies if edge.caller_implementation_id == ids["CheckDatabase"])


def test_ambiguous_source_definitions_and_cycles_block_selected_plan(tmp_path):
    conn, config, profile, migration, closures, _, _, helper, leaf = with_utilities(tmp_path)
    other = Path(config.source_root) / "Kiosk/src/org/example/Helper.java"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text(helper.read_text())
    inventory = build_component_inventory(config.source_root, "enterprise")
    persist_component_inventory(conn, config.run_id, inventory)
    assert any("Ambiguous" in issue for issue in prepare_library_plan(conn, config, profile, migration).diagnostics)
    other.unlink()
    leaf.write_text("package org.example; public class Leaf { public static int value() { return Helper.value(); } }")
    inventory = build_component_inventory(config.source_root, "enterprise")
    persist_component_inventory(conn, config.run_id, inventory)
    assert any("cycle" in issue.lower() for issue in prepare_library_plan(conn, config, profile, migration).diagnostics)


def test_java_utilities_follow_thresholds_and_dependency_first_schedule(tmp_path):
    conn, config, profile, migration, closures, inventory, libraries, _, _ = with_utilities(tmp_path)
    ids = identities(inventory)
    assert libraries.assignments["implementation:" + ids["Helper"]].startswith("shared-")
    enqueue_closure_conversions(conn, config, closures)
    rows = conn.execute("SELECT * FROM agent_tasks").fetchall()
    ordered = ordered_conversion_tasks(conn, config, rows)
    names = [json.loads(row["input_json"])["conversion_id"] for row in ordered]
    assert names.index("org.example.Leaf") < names.index("org.example.Helper") < names.index("org.example.CheckDatabase")
    assert names.count("org.example.Helper") == 1
    assert names.count("org.example.Leaf") == 1


def test_cross_library_dependencies_are_planned_without_changing_thresholds(tmp_path):
    conn, config, profile, migration, _, inventory, _, _, _ = with_utilities(tmp_path, calls=3)
    profile.broad_library_usage_threshold = 5
    libraries = prepare_library_plan(conn, config, profile, migration)
    ids = identities(inventory)
    parent = libraries.assignments["implementation:" + ids["CheckDatabase"]]
    assert parent.startswith("shared-")
    assert libraries.assignments["implementation:" + ids["Helper"]] == "common-lib"
    assert libraries.library_dependencies[parent] == ["common-lib"]
    assert libraries.library_build_order.index("common-lib") < libraries.library_build_order.index(parent)
    assert not libraries.diagnostics


def test_changed_original_utility_blocks_stale_scheduling(tmp_path):
    conn, config, _, _, closures, _, _, helper, _ = with_utilities(tmp_path)
    helper.write_text(helper.read_text() + "// changed")
    with pytest.raises(ValueError, match="changed after inventory"):
        enqueue_closure_conversions(conn, config, closures)


def test_runtime_passes_converted_utility_apis_and_rechecks_changes(monkeypatch, tmp_path):
    conn, config, profile, migration, closures, _, _, _, _ = with_utilities(tmp_path)
    enqueue_closure_conversions(conn, config, closures)
    conn.execute("DELETE FROM agent_tasks WHERE scope_id='org.example.StringFormatter'")
    conn.commit()
    monkeypatch.setattr("runtime.managed_projects.create_build_context", factory)
    calls = []
    def convert(self, instruction, payload):
        data = json.loads(payload)
        calls.append(data)
        return json.dumps(dict(java_source=data["primary_source_content"], dependencies=[]))
    monkeypatch.setattr("runtime.managed_projects.AdkExecutor.execute", convert)
    assert run_managed_tasks(conn, config, profile, migration)["failed"] == 0
    names = [item["conversion_id"] for item in calls]
    assert names.index("org.example.Leaf") < names.index("org.example.Helper") < names.index("org.example.CheckDatabase")
    caller = next(item for item in calls if item["conversion_id"] == "org.example.CheckDatabase")
    assert caller["converted_dependency_apis"][0]["logical_id"] == "org.example.Helper"
    evidence = collect_component_evidence(conn, config, profile)
    assert not [issue for item in evidence for issue in item["issues"]]
    utility = next(item for item in evidence if item["conversion_id"] == "org.example.Helper")
    path = Path(utility["source_path"])
    path.write_text(path.read_text() + "// changed native API evidence")
    refreshed = collect_component_evidence(conn, config, profile)
    assert any("Native utility APIs changed" in issue for item in refreshed for issue in item["issues"])


def test_local_utility_does_not_cover_another_operation(tmp_path):
    from runtime.shared_libraries.ownership import task_covers
    data = dict(managed_project_operation="WebOp", channel="WEB", consumer_operations=["WEB/WebOp", "KIOSK/KioskOp"])
    assert task_covers(data, "WebOp", "WEB")
    assert not task_covers(data, "KioskOp", "KIOSK")


def test_reinventorying_utility_changes_reschedules_unchanged_callers(tmp_path):
    conn, config, profile, migration, closures, _, _, helper, _ = with_utilities(tmp_path)
    enqueue_closure_conversions(conn, config, closures)
    original = json.loads(conn.execute("SELECT input_json FROM agent_tasks WHERE scope_id='org.example.CheckDatabase'").fetchone()[0])
    conn.execute("UPDATE agent_tasks SET status='completed'")
    conn.commit()
    helper.write_text(helper.read_text() + "// source revision")
    persist_component_inventory(conn, config.run_id, build_component_inventory(config.source_root, "enterprise"))
    prepare_library_plan(conn, config, profile, migration)
    enqueue_closure_conversions(conn, config, closures)
    row = conn.execute("SELECT status,input_json FROM agent_tasks WHERE scope_id='org.example.CheckDatabase'").fetchone()
    updated = json.loads(row["input_json"])
    assert row["status"] == "pending"
    assert updated["primary_source_content"] == original["primary_source_content"]
    assert updated["dependency_source_hash"] != original["dependency_source_hash"]


def test_source_dependency_order_handles_deep_chains_without_recursion():
    from tools.component_inventory_tools.dependency_order import dependency_first_order
    nodes = {str(index) for index in range(2000)}
    dependencies = {str(index): {str(index + 1)} for index in range(1999)}
    result = dependency_first_order(nodes, dependencies)
    assert result[0] == "1999"
    assert result[-1] == "0"


def test_utility_library_poms_receive_planned_dependencies(tmp_path):
    from xml.etree import ElementTree
    from runtime.shared_libraries.projects import create_library_contexts
    from constants import COMMON_LIB_ARTIFACT_ID
    conn, config, profile, migration, _, inventory, _, _, _ = with_utilities(tmp_path, calls=3)
    profile.broad_library_usage_threshold = 5
    plan = prepare_library_plan(conn, config, profile, migration)
    contexts = {(packet.operation_id, packet.channel): factory(profile, Path(config.output_root) / packet.channel / packet.operation_id, packet.operation_id)
                for packet in migration.batches[0].task_packets}
    libraries = create_library_contexts(conn, config, profile, contexts, factory)
    ids = identities(inventory)
    owner = plan.assignments["implementation:" + ids["CheckDatabase"]]
    dependencies = ElementTree.parse(libraries[owner].pom_path).getroot().findall("{*}dependencies/{*}dependency")
    assert any(node.findtext("{*}artifactId") == COMMON_LIB_ARTIFACT_ID for node in dependencies)
    from runtime.shared_libraries.dependencies import ordered_review_projects
    roots = [str(Path(context.pom_path).parent) for context in libraries.values()]
    order = ordered_review_projects(conn, config, roots)
    assert Path(order[0]).name == "common-lib"
