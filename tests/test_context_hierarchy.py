from __future__ import annotations

import pytest

from tools.conversion_tools.context_hierarchy_resolver_tool import (
    PreconditionError,
    build_all_context_hierarchies,
    get_context_hierarchy,
)
from tools.shared_artifact_classifier_tools.classifier import run_shared_artifact_classification
from tools.state_store_tools._json import loads
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.source_artifacts import get_source_artifact, upsert_source_artifact


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def mark_inventory_complete(conn):
    upsert_run(
        conn,
        run_id=RUN_ID,
        run_mode="single_channel",
        status="started",
        current_phase="INVENTORY_COMPLETE=true",
    )


def add_context(conn, context_id: str, parent_id: str | None):
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:context:{context_id}",
        run_id=RUN_ID,
        kind="context",
        logical_id=context_id,
        source_hash=f"hash-{context_id}",
        used_by_ids=["OpA"],
        metadata={"id": context_id, "parent_id": parent_id},
    )


def test_precondition_requires_inventory_complete():
    conn = memory_conn()

    with pytest.raises(PreconditionError):
        build_all_context_hierarchies(conn, RUN_ID)


def test_flat_context_has_self_chain_and_root():
    conn = memory_conn()
    mark_inventory_complete(conn)
    add_context(conn, "BaseContext", None)

    hierarchies = build_all_context_hierarchies(conn, RUN_ID)

    assert hierarchies[0].chain == ["BaseContext"]
    assert hierarchies[0].root_id == "BaseContext"
    assert get_context_hierarchy(conn, "BaseContext", RUN_ID).chain == ["BaseContext"]


def test_two_level_context_chain():
    conn = memory_conn()
    mark_inventory_complete(conn)
    add_context(conn, "ParentContext", None)
    add_context(conn, "ChildContext", "ParentContext")

    build_all_context_hierarchies(conn, RUN_ID)

    hierarchy = get_context_hierarchy(conn, "ChildContext", RUN_ID)
    assert hierarchy.chain == ["ChildContext", "ParentContext"]
    assert hierarchy.root_id == "ParentContext"


def test_three_level_context_chain():
    conn = memory_conn()
    mark_inventory_complete(conn)
    add_context(conn, "GrandparentContext", None)
    add_context(conn, "ParentContext", "GrandparentContext")
    add_context(conn, "ChildContext", "ParentContext")

    build_all_context_hierarchies(conn, RUN_ID)

    hierarchy = get_context_hierarchy(conn, "ChildContext", RUN_ID)
    assert hierarchy.chain == ["ChildContext", "ParentContext", "GrandparentContext"]
    assert hierarchy.root_id == "GrandparentContext"


def test_cycle_records_partial_chain_and_human_review_task():
    conn = memory_conn()
    mark_inventory_complete(conn)
    add_context(conn, "A", "B")
    add_context(conn, "B", "C")
    add_context(conn, "C", "A")

    build_all_context_hierarchies(conn, RUN_ID)

    hierarchy = get_context_hierarchy(conn, "A", RUN_ID)
    assert hierarchy.has_cycle is True
    assert hierarchy.chain == ["A", "B", "C"]
    task = conn.execute(
        """
        SELECT * FROM agent_tasks
        WHERE run_id = ? AND scope_type = 'context' AND scope_id = 'A'
        """,
        (RUN_ID,),
    ).fetchone()
    assert task["status"] == "needs_human_review"
    assert task["blocking_reason"] == "context_cycle"


def test_shared_artifact_classification_identifies_shared_formats_and_classes():
    conn = memory_conn()
    mark_inventory_complete(conn)
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:format:StandardHeaderFmt",
        run_id=RUN_ID,
        kind="format",
        logical_id="StandardHeaderFmt",
        source_hash="hash-format",
        used_by_ids=["OpA", "OpB"],
        metadata={"id": "StandardHeaderFmt"},
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:java_class:SharedClass",
        run_id=RUN_ID,
        kind="java_class",
        logical_id="SharedClass",
        source_hash="hash-class",
        used_by_ids=["StepA", "StepB"],
        metadata={"id": "SharedClass"},
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:context:SharedContext",
        run_id=RUN_ID,
        kind="context",
        logical_id="SharedContext",
        source_hash="hash-context",
        used_by_ids=["OpA", "OpB"],
        metadata={"id": "SharedContext"},
    )

    summary = run_shared_artifact_classification(conn, RUN_ID)

    assert summary.shared_formats == 1
    assert summary.shared_classes == 1
    assert summary.shared_contexts == 1
    assert summary.xml_contract_candidates == 1
    format_artifact = get_source_artifact(conn, f"{RUN_ID}:format:StandardHeaderFmt")
    assert format_artifact["shared"] == 1
    assert loads(conn.execute(
        "SELECT metadata_json FROM source_artifacts WHERE artifact_id = ?",
        (f"{RUN_ID}:format:StandardHeaderFmt",),
    ).fetchone()["metadata_json"])["xml_contract_candidate"] is True
