from __future__ import annotations

from pathlib import Path

import pytest

from tools.conversion_tools.context_field_resolver_tool import (
    CycleDetectedError,
    resolve_context_fields,
)
from tools.state_store_tools.context_hierarchies import upsert_context_hierarchy
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.source_artifacts import upsert_source_artifact


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def add_operation(conn, operation_id: str, context_id: str, format_id: str, steps: list[str]):
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:operation:{operation_id}",
        run_id=RUN_ID,
        kind="operation",
        logical_id=operation_id,
        metadata={
            "id": operation_id,
            "operation_context": context_id,
            "ref_formats": {"csRequestFormat": format_id},
            "steps": steps,
        },
    )


def add_format(conn, tmp_path: Path, format_id: str, tag: str, field: str):
    note = tmp_path / f"{format_id}.md"
    note.write_text(f"## Structure\n<{tag} dataName=\"{field}\"/>\n", encoding="utf-8")
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:format:{format_id}",
        run_id=RUN_ID,
        kind="format",
        logical_id=format_id,
        source_path=str(note),
        metadata={"id": format_id},
    )


def add_opstep_and_java(conn, composer_root: Path, opstep_id: str, fqcn: str):
    source = composer_root / Path(*fqcn.split(".")).with_suffix(".java")
    source.parent.mkdir(parents=True)
    source.write_text(
        """
package com.bank.ops;
public class StepA {
  public int execute(Context context) {
    context.setValueAt("ImplWritten", "x");
    context.getValueAt("ImplRead");
    return 0;
  }
}
""",
        encoding="utf-8",
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:opStep:{opstep_id}",
        run_id=RUN_ID,
        kind="opStep",
        logical_id=opstep_id,
        metadata={"id": opstep_id, "impl_class": fqcn},
    )


def test_single_context_collects_fields_from_formats_and_implclasses(tmp_path: Path):
    conn = memory_conn()
    upsert_context_hierarchy(conn, context_id="LeafContext", run_id=RUN_ID, chain=["LeafContext"], root_id="LeafContext")
    add_format(conn, tmp_path, "RequestFmt", "CCDate", "BusinessDate")
    add_opstep_and_java(conn, tmp_path / "composer", "StepA", "com.bank.ops.StepA")
    add_operation(conn, "OpA", "LeafContext", "RequestFmt", ["StepA"])

    inventory = resolve_context_fields(conn, "LeafContext", "INTERNET", RUN_ID, str(tmp_path / "composer"))

    fields = {field.name: field for field in inventory.fields}
    assert fields["BusinessDate"].inferred_type == "LocalDate"
    assert fields["BusinessDate"].source == "formatter"
    assert fields["ImplWritten"].written_by == ["StepA"]
    assert fields["ImplRead"].read_by == ["StepA"]


def test_two_level_chain_marks_inherited_and_deduplicates_to_leaf(tmp_path: Path):
    conn = memory_conn()
    upsert_context_hierarchy(
        conn,
        context_id="LeafContext",
        run_id=RUN_ID,
        chain=["LeafContext", "BaseContext"],
        root_id="BaseContext",
    )
    add_format(conn, tmp_path, "LeafFmt", "CCString", "ClientId")
    add_format(conn, tmp_path, "BaseFmt", "CCBoolean", "ClientId")
    add_operation(conn, "LeafOp", "LeafContext", "LeafFmt", [])
    add_operation(conn, "BaseOp", "BaseContext", "BaseFmt", [])

    inventory = resolve_context_fields(conn, "LeafContext", "INTERNET", RUN_ID, str(tmp_path))

    fields = {field.name: field for field in inventory.fields}
    assert fields["ClientId"].context_level == "LeafContext"
    assert fields["ClientId"].inferred_type == "String"
    assert fields["ClientId"].inherited is False


def test_context_cycle_raises_cycle_detected_error():
    conn = memory_conn()
    upsert_context_hierarchy(
        conn,
        context_id="LeafContext",
        run_id=RUN_ID,
        chain=["LeafContext", "BaseContext"],
        root_id="BaseContext",
        has_cycle=True,
    )

    with pytest.raises(CycleDetectedError):
        resolve_context_fields(conn, "LeafContext", "INTERNET", RUN_ID, ".")
