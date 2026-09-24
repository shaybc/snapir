from __future__ import annotations

from tools.conversion_tools.channel_filter_tool import filter_opsteps_for_channel
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.source_artifacts import upsert_source_artifact


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def add_operation(conn):
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:operation:OpA",
        run_id=RUN_ID,
        kind="operation",
        logical_id="OpA",
        metadata={"id": "OpA", "steps": ["StepA", "StepB", "StepC", "StepD"]},
    )


def add_opstep(conn, opstep_id: str, only_for: str | None):
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:opStep:{opstep_id}",
        run_id=RUN_ID,
        kind="opStep",
        logical_id=opstep_id,
        metadata={"id": opstep_id, "only_for": only_for},
    )


def test_filter_opsteps_for_channel_preserves_order_and_only_excludes_steps():
    conn = memory_conn()
    add_operation(conn)
    add_opstep(conn, "StepA", None)
    add_opstep(conn, "StepB", "IVR")
    add_opstep(conn, "StepC", "internet,IVR")
    add_opstep(conn, "StepD", "")

    included, excluded = filter_opsteps_for_channel(conn, "OpA", "INTERNET", RUN_ID)

    assert included == ["StepA", "StepC", "StepD"]
    assert [step.id for step in excluded] == ["StepB"]
