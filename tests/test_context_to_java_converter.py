from __future__ import annotations

import subprocess
from pathlib import Path

from agents.source_conversion.context_to_java_converter.agent import (
    build_context_java_class,
    get_context_inventory,
    run_context_to_java_converter_task,
    sanitize_java_identifier,
    submit_context_class,
)
from models.conversion_models import ContextField, ContextFieldInventory
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.context_field_inventories import upsert_context_field_inventory
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.native_java_artifacts import get_native_java_artifact


RUN_ID = "run-1"
TASK_ID = "task-context-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def compiled(returncode: int, stderr: str = ""):
    return subprocess.CompletedProcess(args=["javac"], returncode=returncode, stdout="", stderr=stderr)


def context_field(
    name: str,
    java_type: str = "String",
    context_level: str = "LeafContext",
    inherited: bool = False,
) -> ContextField:
    return ContextField(
        name=name,
        context_level=context_level,
        source="formatter",
        inferred_type=java_type,
        inherited=inherited,
    )


def inventory(fields: list[ContextField]) -> ContextFieldInventory:
    return ContextFieldInventory(
        context_id="LeafContext",
        channel="INTERNET",
        full_chain=["LeafContext"],
        fields=fields,
    )


def add_inventory(conn, inv: ContextFieldInventory):
    upsert_context_field_inventory(
        conn,
        context_id=inv.context_id,
        channel=inv.channel,
        run_id=RUN_ID,
        full_chain=inv.full_chain,
        inventory=inv.model_dump(mode="json"),
        status="ready",
    )


def add_task(conn):
    upsert_agent_task(
        conn,
        task_id=TASK_ID,
        run_id=RUN_ID,
        agent_name="ContextToJavaConverterAgent",
        scope_type="context",
        scope_id="LeafContext",
        channel="INTERNET",
        target_language="java",
        status="pending",
        input_data={
            "conversion_id": "LeafContext",
            "kind": "xml_context",
            "channel": "INTERNET",
            "primary_source_content": "",
            "relationship_context": "context",
            "target_kind": "java_context",
        },
    )


def test_single_level_context_generates_flat_class_without_inherited_comments():
    java_source = build_context_java_class(inventory([
        context_field("clientId"),
        context_field("active", "boolean"),
    ]))

    assert "package com.company.generated.context;" in java_source
    assert "public class LeafContext" in java_source
    assert "extends" not in java_source
    assert "@" not in java_source
    assert "private String clientId;" in java_source
    assert "private boolean active;" in java_source
    assert "public String getClientId()" in java_source
    assert "public void setClientId(String value)" in java_source
    assert "// inherited from" not in java_source


def test_two_level_context_adds_inherited_comments():
    inv = ContextFieldInventory(
        context_id="LeafContext",
        channel="INTERNET",
        full_chain=["LeafContext", "BaseContext"],
        fields=[
            context_field("clientId"),
            context_field("traceId", context_level="BaseContext", inherited=True),
        ],
    )

    java_source = build_context_java_class(inv)

    assert "// inherited from BaseContext" in java_source
    assert "private String traceId;" in java_source


def test_field_name_is_sanitized_to_java_identifier():
    assert sanitize_java_identifier("Client ID") == "clientID"
    assert sanitize_java_identifier("123 Client-ID") == "field123ClientID"

    java_source = build_context_java_class(inventory([context_field("Client ID")]))

    assert "private String clientID;" in java_source
    assert "getClientID()" in java_source


def test_local_date_field_generates_import():
    java_source = build_context_java_class(inventory([context_field("businessDate", "LocalDate")]))

    assert "import java.time.LocalDate;" in java_source
    assert "private LocalDate businessDate;" in java_source


def test_get_context_inventory_reads_prebuilt_inventory():
    conn = memory_conn()
    inv = inventory([context_field("clientId")])
    add_inventory(conn, inv)

    loaded = get_context_inventory(conn, "LeafContext", "INTERNET", RUN_ID)

    assert loaded.context_id == "LeafContext"
    assert loaded.fields[0].name == "clientId"


def test_submit_context_class_records_converted_artifact(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    add_task(conn)
    monkeypatch.setattr(
        "agents.source_conversion.context_to_java_converter.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = submit_context_class(conn, TASK_ID, "class LeafContext {}", str(tmp_path / "LeafContext.java"), RUN_ID)

    assert result == "compiled"
    assert get_agent_task(conn, TASK_ID)["status"] == "completed"
    artifact = get_native_java_artifact(conn, f"{RUN_ID}:native_java:{TASK_ID}")
    assert artifact["kind"] == "xml_context"
    assert artifact["status"] == "converted"


def test_mock_context_converter_runner(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    inv = inventory([context_field("clientId")])
    add_inventory(conn, inv)
    add_task(conn)
    monkeypatch.setattr(
        "agents.source_conversion.context_to_java_converter.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = run_context_to_java_converter_task(
        conn,
        TASK_ID,
        "LeafContext",
        "INTERNET",
        RUN_ID,
        str(tmp_path / "LeafContext.java"),
        build_context_java_class,
    )

    assert result == "compiled"
