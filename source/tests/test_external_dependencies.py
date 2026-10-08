"""Check external library contracts, null references, and documented prompt evidence."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from models.external_dependency import ExternalDependencyRule
from models.pipeline_configuration import PipelineConfiguration
from runtime.composer_behavior_context import behavior_context
from runtime.shared_libraries.registry import conversion_hash
from tools.component_inventory_tools.composer_values import reference_value
from tools.conversion_tools.external_dependency_resolver import external_dependency
from tools.conversion_tools.closure_builder_tool import build_operation_closure
from tests.test_closure_builder import add_ready_fixture, RUN_ID


def test_exact_class_precedes_package_and_package_boundary():
    broad = ExternalDependencyRule(package_prefix="vendor.base", treatment="retain")
    exact = ExternalDependencyRule(class_name="vendor.base.Type", treatment="replace", behavior_description="Preserve the supplied field values")
    assert external_dependency("vendor.base.Type", [broad, exact], None, "test")["treatment"] == "replace"
    assert external_dependency("vendor.baseline.Type", [broad], None, "test") is None


def test_document_sections_preserve_nested_behavior_and_hash(tmp_path):
    manual = tmp_path / "manual.md"
    manual.write_text("## Context\nMap values.\n### Access\nUse keys.\n## Other\nUnrelated.", encoding="utf-8")
    evidence = behavior_context(manual, ["Context"])[0]
    assert "Use keys" in evidence["content"] and "Unrelated" not in evidence["content"]
    assert evidence["content_hash"] and evidence["document"] == str(manual.resolve())
    with pytest.raises(ValueError, match="heading"):
        behavior_context(manual, ["Absent"])


def test_shared_document_excerpts_are_sent_once(tmp_path):
    from runtime.composer_behavior_context import compact_behavior_evidence
    manual = tmp_path / "manual.md"
    manual.write_text("## Context\nUse configured fields.", encoding="utf-8")
    evidence = behavior_context(manual, ["Context"])
    records, documents = compact_behavior_evidence([dict(class_name="vendor.A", behavior_evidence=evidence), dict(class_name="vendor.B", behavior_evidence=evidence)])
    assert len(documents) == 1
    assert all("content" not in item["behavior_evidence"][0] for item in records)


@pytest.mark.parametrize("treatment", ["retain", "replace"])
def test_declared_vendor_superclass_is_recorded_without_source(tmp_path, treatment):
    conn, root, vault = add_ready_fixture(tmp_path)
    (root / "com/bank/CCString.java").write_text("package com.bank; import vendor.base.Element; public class CCString extends Element {}")
    profile = PipelineConfiguration(external_dependencies=[dict(class_name="vendor.base.Element", treatment=treatment,
        behavior_description="Read and write configured fields", maven_coordinates="vendor:base:1")])
    result = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(root), str(vault),
        classpath_index=SimpleNamespace(classes={}, issues=[]), profile=profile)
    assert result.status.value == "READY"
    assert {item["class_name"] for item in result.external_dependencies} == {"vendor.base.Element"}
    assert all(item.logical_id != "vendor.base.Element" for item in result.conversion_components)


def test_legacy_document_choices_do_not_override_required_behavior(tmp_path):
    conn, root, vault = add_ready_fixture(tmp_path)
    (root / "com/bank/CCString.java").write_text("package com.bank; import vendor.base.Element; public class CCString extends Element {}")
    manual = tmp_path / "manual.md"
    manual.write_text("## Context\nValues.", encoding="utf-8")
    profile = PipelineConfiguration(composer_behavior_document=str(manual), external_dependencies=[dict(
        class_name="vendor.base.Element", treatment="replace", behavior_sections=["Missing"], behavior_description="Read configured fields")])
    result = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(root), str(vault),
        classpath_index=SimpleNamespace(classes={}, issues=[]), profile=profile)
    assert result.status.value == "READY"
    assert len(result.composer_behavior_evidence) == 4
    assert "composer_behavior_document" not in profile.model_dump()
    assert "behavior_sections" not in profile.external_dependencies[0].model_dump()


def test_reference_nil_and_literal_field_data(tmp_path):
    from tools.component_inventory_tools.xml_documents import read_xml
    assert reference_value(" NIL ") is None
    xml = tmp_path / "data.xml"
    xml.write_text('<XML><field value="nil">nil</field></XML>')
    field = read_xml(xml)[0]
    assert field.get("value") == field.text == "nil"


def test_conversion_context_is_required_without_external_rules():
    from runtime.composer_behavior_context import attach_composer_behavior, COMPOSER_SECTIONS
    request = attach_composer_behavior({"external_dependencies": [], "composer_behavior_evidence": []})
    assert tuple(item["heading"] for item in request["composer_behavior_evidence"]) == COMPOSER_SECTIONS
    assert all(item["content"] for item in request["composer_behavior_evidence"])


def test_required_evidence_is_not_repeated_in_relationship_context():
    import json
    from runtime.composer_behavior_context import attach_composer_behavior
    request = attach_composer_behavior({"relationship_context": json.dumps({"operation_id": "Op", "composer_behavior_evidence": ["old excerpt"]})})
    assert json.loads(request["relationship_context"]) == {"operation_id": "Op"}
    assert len(request["composer_behavior_evidence"]) == 4


def test_conversion_context_does_not_require_manual_file(monkeypatch, tmp_path):
    from runtime.composer_behavior_context import attach_composer_behavior
    document = tmp_path / "docs/comp-manual/wsbcc_developer_manual_v2.md"
    document.parent.mkdir(parents=True)
    document.write_text("## 5. Context\nFields.", encoding="utf-8")
    monkeypatch.setattr("runtime.project_paths.project_root", lambda: tmp_path)
    document.unlink()
    request = attach_composer_behavior({})
    assert len(request["composer_behavior_evidence"]) == 4
    assert all(item["document"] == "embedded:composer_conversion_knowledge" for item in request["composer_behavior_evidence"])
    assert "opStep" in request["composer_behavior_evidence"][0]["content"]


def test_declared_external_opstep_does_not_require_java_source(tmp_path):
    conn, root, vault = add_ready_fixture(tmp_path)
    (root / "com/bank/ops/StepA.java").unlink()
    profile = PipelineConfiguration(external_dependencies=[dict(class_name="com.bank.ops.StepA", treatment="retain")])
    result = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(root), str(vault),
        classpath_index=SimpleNamespace(classes={}, issues=[]), profile=profile)
    assert result.status.value == "READY"
    assert any(item["class_name"] == "com.bank.ops.StepA" for item in result.external_dependencies)


def test_retained_client_declaration_reaches_existing_build_checks():
    profile = PipelineConfiguration(external_dependencies=[dict(class_name="vendor.Client", treatment="retain", maven_coordinates="vendor:client:1.0")])
    assert "vendor.Client" in profile.allowed_ibm_classes
    assert "vendor:client:1.0" in profile.allowed_ibm_artifacts


def test_behavior_evidence_changes_conversion_reuse_identity():
    profile = PipelineConfiguration()
    data = dict(kind="ibm_java", primary_source_content="class Example {}")
    original = conversion_hash(data, profile)
    data["external_dependencies"] = [dict(class_name="vendor.Type", treatment="replace", behavior_description="Read a value")]
    assert conversion_hash(data, profile) != original


def test_xml_contexts_without_implementations_and_nil_parent_are_valid(tmp_path):
    from tests.test_component_inventory import make_workspace
    from tools.component_inventory_tools import build_component_inventory
    workspace, _ = make_workspace(tmp_path)
    xml = workspace / "Web/src/Channel/WEB/operation.xml"
    xml.write_text(xml.read_text().replace('id="WebOp"', 'id="WebOp" operationContext="Data"').replace("</XML>", '<context id="Data" parent="nil"><CCString dataName="Name"/></context></XML>'))
    inventory = build_component_inventory(workspace, "test")
    contexts = [use for use in inventory.uses if use.component_kind == "context"]
    assert contexts and all(use.resolution_issue is None for use in contexts)
    assert not any("reference: nil" in value for value in inventory.diagnostics)


def test_automatic_framework_boundary_and_explicit_override():
    name = "com.ibm.dse.base.Element"
    assert external_dependency(name, [], None, "test", allow_framework=True)["treatment"] == "replace"
    assert external_dependency("com.ibm.dse.baseline.Element", [], None, "test", allow_framework=True) is None
    assert external_dependency(name, [], None, "test") is None
    rule = ExternalDependencyRule(class_name=name, treatment="retain")
    assert external_dependency(name, [rule], None, "test", allow_framework=True)["treatment"] == "retain"
