"""Collect configured whole formats/steps and verify source/configuration freshness."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_component_inventory import make_workspace, store
from tools.component_inventory_tools import build_component_inventory
from tools.conversion_tools.behavior_unit_builder import build_behavior_units
from tools.state_store_tools.source_artifacts import upsert_source_artifact


def setup(tmp_path, same=False, internal_format=False):
    workspace, java = make_workspace(tmp_path)
    if same:
        path = workspace / "Kiosk/src/Channel/KIOSK/operation.xml"
        path.write_text(path.read_text(encoding="utf-8").replace('parameter="kiosk"', 'parameter="web"').replace('refid="FormatB"', 'refid="FormatA"'), encoding="utf-8")
    if internal_format:
        path = workspace / "Web/src/Channel/WEB/operation.xml"
        path.write_text(path.read_text(encoding="utf-8").replace('on0Do="end"/>',
            'on0Do="end"><refFormat name="inner" refid="FormatB"/></opStep>'), encoding="utf-8")
    inventory = build_component_inventory(workspace, "enterprise")
    conn = store(inventory)
    for channel, name, fmt in (("WEB", "WebOp", "FormatA"), ("KIOSK", "KioskOp", "FormatA" if same else "FormatB")):
        upsert_source_artifact(conn, artifact_id=name, run_id="run-1", kind="operation", logical_id=name,
            metadata=dict(channel=channel, ref_formats={"csRequestFormat": fmt}))
    components = [dict(kind="ibm_java", logical_id=item.package_name + "." + item.class_name,
        source_file=str(workspace / item.source_path), source_hash=item.source_hash, source_content="") for item in inventory.implementations]
    closure = dict(status="READY", conversion_components_checked=True, blocking_issues=[], conversion_components=components,
        operation_id="WebOp", channel="WEB", included_opstep_ids=["CheckDatabase"], ref_formats={"csRequestFormat": "FormatA"}, external_dependencies=[])
    return conn, SimpleNamespace(source_root=str(workspace), run_id="run-1"), closure, java


def test_one_task_for_full_format_and_one_for_configured_step(tmp_path):
    conn, config, closure, java = setup(tmp_path)
    units, bindings = build_behavior_units(conn, config, closure)
    assert {item.kind for item in units} == {"configured_step", "request_unformat"}
    assert len(units) == 2 and len(bindings) == 2
    formatted = next(item for item in units if item.kind == "request_unformat")
    assert '<fmtDef id="FormatA"' in formatted.configuration_xml
    assert "CCString" in formatted.configuration_xml
    assert formatted.sources[0].identity == "org.example.StringFormatter"
    assert all(item.kind not in {"formatter", "decorator", "context"} for item in units)


def test_compatible_reuse_counts_consumers_outside_selected_operation(tmp_path):
    conn, config, closure, java = setup(tmp_path, same=True)
    units, _ = build_behavior_units(conn, config, closure)
    assert all(item.consumers == ["KIOSK/KioskOp", "WEB/WebOp"] for item in units)


def test_different_configuration_is_not_counted_as_same_step(tmp_path):
    conn, config, closure, java = setup(tmp_path)
    units, _ = build_behavior_units(conn, config, closure)
    assert next(item for item in units if item.kind == "configured_step").consumers == ["WEB/WebOp"]


def test_changed_implementation_or_xml_is_rejected_before_model_execution(tmp_path):
    conn, config, closure, java = setup(tmp_path)
    java.write_text(java.read_text(encoding="utf-8").replace("true", "false"), encoding="utf-8")
    with pytest.raises(ValueError, match="changed after dependency"):
        build_behavior_units(conn, config, closure)
    for item in closure["conversion_components"]:
        item["source_hash"] = hashlib.sha256(Path(item["source_file"]).read_bytes()).hexdigest()
    path = Path(config.source_root) / "Web/src/Channel/WEB/operation.xml"
    path.write_text(path.read_text(encoding="utf-8").replace('parameter="web"', 'parameter="changed"'), encoding="utf-8")
    with pytest.raises(ValueError, match="XML changed since intake"):
        build_behavior_units(conn, config, closure)


def test_unchecked_closure_cannot_be_used_for_native_conversion(tmp_path):
    conn, config, closure, java = setup(tmp_path)
    closure["conversion_components_checked"] = False
    with pytest.raises(ValueError, match="checked READY"):
        build_behavior_units(conn, config, closure)


def test_step_bundle_contains_internally_referenced_format_and_implementation(tmp_path):
    conn, config, closure, java = setup(tmp_path, internal_format=True)
    units, _ = build_behavior_units(conn, config, closure)
    step = next(item for item in units if item.kind == "configured_step")
    assert {item["logical_id"] for item in step.referenced_definitions} == {"FormatB"}
    assert {item.identity for item in step.sources} == {"org.example.CheckDatabase", "org.example.StringFormatter"}
    assert step.consumers == ["WEB/WebOp"]


def test_changed_tag_mapping_does_not_reuse_old_implementation(tmp_path):
    conn, config, closure, java = setup(tmp_path)
    path = Path(config.source_root) / "Common/src/Channel/XML/dse.ini"
    path.write_text(path.read_text(encoding="utf-8").replace("org.example.StringFormatter", "other.Formatter"), encoding="utf-8")
    with pytest.raises(ValueError, match="tag mapping changed"):
        build_behavior_units(conn, config, closure)
