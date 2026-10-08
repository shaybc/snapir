from __future__ import annotations

import subprocess
from pathlib import Path

from agents.source_conversion.native_java_reviewer.agent import (
    build_human_gate2_report,
    dispatch_reviews_for_batch,
    parse_review_output,
    review_native_java,
)
from models.common_models import TargetLanguage
from models.conversion_models import ConversionStatus
from models.registry_models import ComponentRegistryRecord
from tools.artifact_registry_tools.component_registry import mark_validated, register_component
from tools.common_lib_tools.build import convert_framework_tags
from tools.common_lib_tools.promotion import maybe_promote
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.native_java_artifacts import (
    get_native_java_artifact,
    upsert_native_java_artifact,
)
from tools.state_store_tools.source_artifacts import upsert_source_artifact
from tools.state_store_tools.tag_registry import upsert_tag


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def component_record(generated_path: str, used_by_validated_operations: int) -> ComponentRegistryRecord:
    return ComponentRegistryRecord(
        component_id="component-1",
        artifact_kind="ibm_java",
        logical_id="SharedImpl",
        source_path="src/SharedImpl.java",
        source_hash="hash-1",
        target_language=TargetLanguage.java,
        artifact_schema_version="v1",
        generated_path=generated_path,
        status=ConversionStatus.validated,
        used_by_operations=["OpA", "OpB"],
        used_by_validated_operations=used_by_validated_operations,
    )


def test_ibm_import_in_converted_class_is_reported():
    result = review_native_java(
        "class Original {}",
        "import com.ibm.websphere.sca.Service;\nclass Converted {}",
    )

    assert result.review_status == "needs_revision"
    assert "com.ibm.websphere.sca.Service" in result.issues[0]


def test_missing_setter_is_reported():
    result = review_native_java(
        "class Original { public void setClientId(String value) {} }",
        "class Converted { }",
    )

    assert result.review_status == "needs_revision"
    assert result.issues == ["Missing setter method: setClientId"]


def test_parse_review_output_reads_json_result():
    result = parse_review_output(
        "conversion-1",
        '{"issues": [], "confidence": "high", "review_status": "approved"}',
    )

    assert result.conversion_id == "conversion-1"
    assert result.review_status == "approved"


def test_approved_dispatch_marks_native_java_artifact_approved(tmp_path: Path):
    conn = memory_conn()
    converted = tmp_path / "Converted.java"
    converted.write_text("class Converted {}", encoding="utf-8")
    upsert_native_java_artifact(
        conn,
        artifact_id="artifact-1",
        run_id=RUN_ID,
        conversion_id="conversion-1",
        kind="ibm_java",
        logical_id="SharedImpl",
        artifact_path=str(converted),
        compiles=True,
        review_status="pending",
        status="converted",
    )

    results = dispatch_reviews_for_batch(
        conn,
        RUN_ID,
        ["artifact-1"],
        reviewer=lambda original, converted_java, review_kind: parse_review_output(
            "conversion-1",
            '{"issues": [], "confidence": "high", "review_status": "approved"}',
        ),
    )

    artifact = get_native_java_artifact(conn, "artifact-1")
    assert results[0].review_status == "approved"
    assert artifact["review_status"] == "approved"


def test_promote_used_by_one_does_not_promote(tmp_path: Path):
    conn = memory_conn()
    generated = tmp_path / "generated" / "Shared.java"
    generated.parent.mkdir()
    generated.write_text("class Shared {}\n", encoding="utf-8")
    register_component(conn, component_record(str(generated), used_by_validated_operations=1))

    assert maybe_promote(conn, "component-1", str(tmp_path / "common-lib"), RUN_ID) is False
    assert not (tmp_path / "common-lib").exists()


def test_promote_used_by_two_copies_and_builds(tmp_path: Path, monkeypatch):
    conn = memory_conn()
    generated = tmp_path / "generated" / "Shared.java"
    generated.parent.mkdir()
    generated.write_text("class Shared {}\n", encoding="utf-8")
    common_lib = tmp_path / "common-lib"
    register_component(conn, component_record(str(generated), used_by_validated_operations=2))
    calls = []

    def fake_build(common_lib_root: str):
        calls.append(common_lib_root)
        return type("Build", (), {"success": True})()

    monkeypatch.setattr("tools.common_lib_tools.promotion.run_common_lib_build", fake_build)

    assert maybe_promote(conn, "component-1", str(common_lib), RUN_ID) is True
    assert (common_lib / "src" / "main" / "java" / "Shared.java").read_text(encoding="utf-8") == "class Shared {}\n"
    assert calls == [str(common_lib)]


def test_mark_validated_can_trigger_common_lib_promotion(tmp_path: Path, monkeypatch):
    conn = memory_conn()
    generated = tmp_path / "generated" / "Shared.java"
    generated.parent.mkdir()
    generated.write_text("class Shared {}\n", encoding="utf-8")
    common_lib = tmp_path / "common-lib"
    register_component(conn, component_record(str(generated), used_by_validated_operations=2))
    monkeypatch.setattr(
        "tools.common_lib_tools.promotion.run_common_lib_build",
        lambda common_lib_root: type("Build", (), {"success": True})(),
    )

    mark_validated(conn, "component-1", common_lib_root=str(common_lib), run_id=RUN_ID)

    assert (common_lib / "src" / "main" / "java" / "Shared.java").exists()


def test_convert_framework_tags_cleans_sources_and_runs_build(tmp_path: Path, monkeypatch):
    conn = memory_conn()
    composer_root = tmp_path / "composer"
    source = composer_root / "com" / "bank" / "CCString.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        "package com.bank;\nimport com.ibm.Legacy;\npublic class CCString {}",
        encoding="utf-8",
    )
    upsert_tag(conn, tag_name="CCString", fqcn="com.bank.CCString", channel="INTERNET", run_id=RUN_ID)
    calls = []
    monkeypatch.setattr(
        "tools.common_lib_tools.build.run_common_lib_build",
        lambda common_lib_root: calls.append(common_lib_root) or type("Build", (), {"success": True})(),
    )

    converted = convert_framework_tags(conn, "INTERNET", str(tmp_path / "common-lib"), str(composer_root), RUN_ID)

    output = tmp_path / "common-lib" / "src" / "main" / "java" / "com" / "bank" / "CCString.java"
    assert converted == ["com.bank.CCString"]
    assert "com.ibm" not in output.read_text(encoding="utf-8")
    assert calls == [str(tmp_path / "common-lib")]


def test_human_gate2_report_counts_review_states():
    report = build_human_gate2_report(
        [
            parse_review_output("a", '{"issues": [], "confidence": "high", "review_status": "approved"}'),
            parse_review_output("b", '{"issues": ["x"], "confidence": "medium", "review_status": "needs_revision"}'),
            parse_review_output("c", '{"issues": ["y"], "confidence": "low", "review_status": "needs_human_review"}'),
        ],
        common_lib_build_passed=True,
        framework_tags_converted=3,
        sample_files=["A.java"],
    )

    assert "Converted files reviewed: 3" in report
    assert "Approved: 1" in report
    assert "Needs revision (auto-retry pending): 1" in report
    assert "Needs human review: 1" in report
    assert "common-lib build: PASSED" in report
    assert "Framework tags converted: 3" in report
