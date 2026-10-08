"""Verify source-origin identity, separate configured behavior and exact consumer counts."""

from pathlib import Path
import shutil

from tools.component_inventory_tools import build_component_inventory
from tools.state_store_tools.component_inventory import persist_component_inventory, get_implementation_usage, get_configured_component_usage
from tools.state_store_tools.db import get_connection, create_all_tables


def make_workspace(tmp_path, *, aliases=False):
    workspace = tmp_path / "workspace"
    for project in ("Common", "Web", "Kiosk"):
        (workspace / project / "src").mkdir(parents=True)
    java = workspace / "Web/src/org/example/CheckDatabase.java"
    java.parent.mkdir(parents=True)
    java.write_text("package org.example; public class CheckDatabase { public boolean available() { return true; } }")
    formatter = workspace / "Common/src/org/example/StringFormatter.java"
    formatter.parent.mkdir(parents=True)
    formatter.write_text("package org.example; public class StringFormatter {}")
    base = workspace / "Common/src/Channel/XML"
    base.mkdir(parents=True)
    (base / "dse.ini").write_text('''<dse.ini><kColl id="settings"><kColl id="tags"><kColl id="formats">
      <field id="CCString" value="org.example.StringFormatter"/></kColl></kColl></kColl></dse.ini>''')
    (base / "formats.xml").write_text('''<XML><fmtDef id="FormatA"><CCString dataName="First"/></fmtDef>
      <fmtDef id="FormatB"><CCString dataName="Second"/></fmtDef>
      <fmtDef id="UnusedFormat"><CCString dataName="Unused"/></fmtDef></XML>''')
    for project, channel, name, fmt, parameter in (("Web", "WEB", "WebOp", "FormatA", "web"),
                                                ("Kiosk", "KIOSK", "KioskOp", "FormatB", "kiosk")):
        path = workspace / project / "src/Channel" / channel
        path.mkdir(parents=True)
        mapping = '<kColl id="tags"><kColl id="opSteps"><field id="CheckDatabase" value="org.example.CheckDatabase"/></kColl></kColl>' if aliases else ""
        (path / "dse.ini").write_text(f'''<dse.ini><kColl id="import"><field id="XML"/></kColl>
          <kColl id="settings">{mapping}</kColl></dse.ini>''')
        implementation = "" if aliases else ' implClass="org.example.CheckDatabase"'
        (path / "operation.xml").write_text(f'''<XML><CCDSEServerOperation id="{name}">
          <opStep id="CheckDatabase"{implementation} parameter="{parameter}" on0Do="end"/>
          <refFormat name="csRequestFormat" refid="{fmt}"/></CCDSEServerOperation></XML>''')
    return workspace, java


def store(inventory):
    conn = get_connection(":memory:")
    create_all_tables(conn)
    persist_component_inventory(conn, "run-1", inventory)
    return conn


def test_same_origin_reused_across_channels_but_configurations_stay_distinct(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    inventory = build_component_inventory(workspace, "enterprise")
    steps = [use for use in inventory.uses if use.component_kind == "opStep"]
    assert len(steps) == 2
    assert len({use.implementation_id for use in steps}) == 1
    assert None not in {use.implementation_id for use in steps}
    assert len({use.configuration_hash for use in steps}) == 2
    assert len({use.definition_id for use in steps}) == 2
    conn = store(inventory)
    summary = next(item for item in get_implementation_usage(conn, "run-1") if item["implementation"]["class_name"] == "CheckDatabase")
    assert (summary["reference_count"], summary["operation_count"], summary["channel_count"]) == (2, 2, 2)


def test_same_class_name_in_different_source_roots_is_not_merged(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    other = workspace / "Kiosk/src/org/example/CheckDatabase.java"
    other.parent.mkdir(parents=True)
    other.write_text("package org.example; public class CheckDatabase {}")
    inventory = build_component_inventory(workspace, "enterprise")
    steps = [use for use in inventory.uses if use.component_kind == "opStep"]
    assert len({use.implementation_id for use in steps}) == 2
    assert all(use.implementation_id for use in steps)


def test_configuration_aliases_do_not_create_duplicate_implementations(tmp_path):
    workspace, _ = make_workspace(tmp_path, aliases=True)
    inventory = build_component_inventory(workspace, "enterprise")
    steps = [use for use in inventory.uses if use.component_kind == "opStep"]
    assert len({use.implementation_id for use in steps}) == 1
    assert len({use.mapping_source for use in steps}) == 2


def test_two_formats_share_formatter_but_not_configured_definition(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    inventory = build_component_inventory(workspace, "enterprise")
    formatters = [use for use in inventory.uses if use.component_kind == "formatter"]
    assert len(formatters) == 2
    assert len({use.implementation_id for use in formatters}) == 1
    assert len({use.configuration_hash for use in formatters}) == 2
    assert all(use.mapping_source.endswith("XML/dse.ini") for use in formatters)


def test_source_edit_changes_hash_not_identity(tmp_path):
    workspace, java = make_workspace(tmp_path)
    before = build_component_inventory(workspace, "enterprise")
    java.write_text(java.read_text().replace("return true", "return false"))
    after = build_component_inventory(workspace, "enterprise")
    first = next(value for value in before.implementations if value.class_name == "CheckDatabase")
    second = next(value for value in after.implementations if value.class_name == "CheckDatabase")
    assert first.implementation_id == second.implementation_id
    assert first.source_hash != second.source_hash


def test_explicit_workspace_identity_survives_checkout_relocation(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    before = build_component_inventory(workspace, "enterprise")
    copied = tmp_path / "another_checkout"
    shutil.copytree(workspace, copied)
    after = build_component_inventory(copied, "enterprise")
    assert {item.implementation_id for item in before.implementations} == {item.implementation_id for item in after.implementations}


def test_unused_configured_definitions_are_preserved_and_snapshot_is_idempotent(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    inventory = build_component_inventory(workspace, "enterprise")
    conn = store(inventory)
    persist_component_inventory(conn, "run-1", inventory)
    assert conn.execute("SELECT COUNT(*) FROM configured_component_uses").fetchone()[0] == len(inventory.uses)
    unused = [value for value in get_configured_component_usage(conn, "run-1") if value["definition"]["logical_id"] == "UnusedFormat"]
    assert len(unused) == 1 and unused[0]["reference_count"] == 0


def test_missing_source_is_explicit_not_a_fabricated_binding(tmp_path):
    workspace, java = make_workspace(tmp_path)
    java.unlink()
    inventory = build_component_inventory(workspace, "enterprise")
    assert all(use.implementation_id is None for use in inventory.uses if use.component_kind == "opStep")
    assert any("Java source is missing: org.example.CheckDatabase" in value for value in inventory.diagnostics)


def test_same_operation_name_in_two_channels_counts_two_consumers(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    path = workspace / "Kiosk/src/Channel/KIOSK/operation.xml"
    path.write_text(path.read_text().replace("KioskOp", "WebOp"))
    conn = store(build_component_inventory(workspace, "enterprise"))
    usage = next(value for value in get_implementation_usage(conn, "run-1") if value["implementation"]["class_name"] == "CheckDatabase")
    assert usage["operation_count"] == 2
    assert len({consumer["operation_id"] for consumer in usage["consumers"]}) == 1


def test_reference_count_is_not_the_same_as_operation_count(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    path = workspace / "Web/src/Channel/WEB/operation.xml"
    source = path.read_text()
    source = source.replace('<refFormat', '<opStep id="CheckAgain" implClass="org.example.CheckDatabase"/><refFormat')
    path.write_text(source)
    conn = store(build_component_inventory(workspace, "enterprise"))
    usage = next(value for value in get_implementation_usage(conn, "run-1") if value["implementation"]["class_name"] == "CheckDatabase")
    assert usage["reference_count"] == 3
    assert usage["operation_count"] == 2


def test_missing_channel_import_is_reported(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    path = workspace / "Web/src/Channel/WEB/dse.ini"
    path.write_text(path.read_text().replace('id="XML"', 'id="ABSENT"'))
    inventory = build_component_inventory(workspace, "enterprise")
    assert any("Missing or ambiguous channel configuration: ABSENT" in issue for issue in inventory.diagnostics)


def test_configuration_edit_changes_config_hash_not_implementation_identity(tmp_path):
    workspace, _ = make_workspace(tmp_path)
    before = build_component_inventory(workspace, "enterprise")
    path = workspace / "Web/src/Channel/WEB/operation.xml"
    path.write_text(path.read_text().replace('parameter="web"', 'parameter="modified"'))
    after = build_component_inventory(workspace, "enterprise")
    first = next(use for use in before.uses if use.channel == "WEB" and use.component_kind == "opStep")
    second = next(use for use in after.uses if use.channel == "WEB" and use.component_kind == "opStep")
    assert first.use_id == second.use_id
    assert first.implementation_id == second.implementation_id
    assert first.configuration_hash != second.configuration_hash
