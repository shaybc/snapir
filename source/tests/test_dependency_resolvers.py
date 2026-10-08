from __future__ import annotations

from pathlib import Path

import pytest

from models.conversion_models import ClosureStatus
from tools.conversion_tools.format_dependency_resolver_tool import resolve_format_dependencies
from tools.conversion_tools.java_impl_resolver_tool import resolve_java_impls
from tools.conversion_tools.operation_xml_loader_tool import (
    OperationXmlNotFoundError,
    load_operation_xml,
)
from tools.state_store_tools.channel_operations import upsert_channel_operation
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.source_artifacts import upsert_source_artifact
from tools.state_store_tools.tag_registry import upsert_tag


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def test_load_operation_xml_returns_raw_xml(tmp_path: Path):
    conn = memory_conn()
    xml_path = tmp_path / "ops" / "OpA.xml"
    xml_path.parent.mkdir()
    xml_path.write_text("<operation/>", encoding="utf-8")
    upsert_channel_operation(
        conn,
        operation_name="OpA",
        channel="INTERNET",
        xml_file_path="ops/OpA.xml",
        run_id=RUN_ID,
    )

    assert load_operation_xml(conn, "OpA", "INTERNET", RUN_ID, str(tmp_path)) == "<operation/>"


def test_load_operation_xml_raises_when_mapping_missing():
    conn = memory_conn()

    with pytest.raises(OperationXmlNotFoundError):
        load_operation_xml(conn, "MissingOp", "INTERNET", RUN_ID, ".")


def test_resolve_format_dependencies_recurses_and_flags_unknown_decorator(tmp_path: Path):
    conn = memory_conn()
    parent = tmp_path / "ParentFmt.md"
    child = tmp_path / "ChildFmt.md"
    parent.write_text(
        """
## Structure
<CCString dataName="ClientId"/>
decorator: <UnknownDecorator/>
## Nested
- refFmt: ChildFmt
""",
        encoding="utf-8",
    )
    child.write_text("## Structure\n<CCDate dataName=\"BusinessDate\"/>\n", encoding="utf-8")
    for format_id, path in {"ParentFmt": parent, "ChildFmt": child}.items():
        upsert_source_artifact(
            conn,
            artifact_id=f"{RUN_ID}:format:{format_id}",
            run_id=RUN_ID,
            kind="format",
            logical_id=format_id,
            source_path=str(path),
            metadata={"id": format_id},
        )
    upsert_tag(conn, tag_name="CCString", fqcn="com.bank.CCString", run_id=RUN_ID)
    upsert_tag(conn, tag_name="CCDate", fqcn="com.bank.CCDate", run_id=RUN_ID)

    format_set = resolve_format_dependencies(conn, ["ParentFmt"], RUN_ID, str(tmp_path))

    assert format_set.all_format_ids == ["ParentFmt", "ChildFmt"]
    assert format_set.decorator_chains["ClientId/CCString"] == ["UnknownDecorator"]
    assert format_set.blocking_issues[0].kind == ClosureStatus.BLOCKED_UNKNOWN_TAG


def test_resolve_java_impls_falls_back_to_tag_registry(tmp_path: Path):
    conn = memory_conn()
    fqcn = "com.bank.ops.StepA"
    source = tmp_path / "com" / "bank" / "ops" / "StepA.java"
    source.parent.mkdir(parents=True)
    source.write_text("package com.bank.ops; public class StepA {}", encoding="utf-8")
    upsert_tag(conn, tag_name="StepTag", fqcn=fqcn, run_id=RUN_ID)
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:opStep:StepA",
        run_id=RUN_ID,
        kind="opStep",
        logical_id="StepA",
        metadata={"id": "StepTag", "impl_class": None},
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:java_class:{fqcn}",
        run_id=RUN_ID,
        kind="java_class",
        logical_id=fqcn,
        metadata={"fqcn": fqcn, "has_ibm_dependency": False},
    )

    refs, issues = resolve_java_impls(conn, ["StepA"], RUN_ID, str(tmp_path))

    assert issues == []
    assert refs[0].fqcn == fqcn


def test_resolve_java_impls_flags_missing_source_file():
    conn = memory_conn()
    fqcn = "com.bank.ops.MissingStep"
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:opStep:StepA",
        run_id=RUN_ID,
        kind="opStep",
        logical_id="StepA",
        metadata={"id": "StepA", "impl_class": fqcn},
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:java_class:{fqcn}",
        run_id=RUN_ID,
        kind="java_class",
        logical_id=fqcn,
        metadata={"fqcn": fqcn, "has_ibm_dependency": False},
    )

    refs, issues = resolve_java_impls(conn, ["StepA"], RUN_ID, ".")

    assert refs == []
    assert issues[0].kind == ClosureStatus.BLOCKED_MISSING_IMPL_CLASS
