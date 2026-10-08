from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tools.state_store_tools.agent_tasks import get_agent_task, make_task_key, upsert_agent_task
from tools.state_store_tools.channel_operations import get_operation, upsert_operation
from tools.state_store_tools.context_field_inventories import (
    get_context_field_inventory,
    upsert_context_field_inventory,
)
from tools.state_store_tools.db import create_all_tables, get_connection, reconcile_on_startup
from tools.state_store_tools.generated_artifacts import (
    get_generated_artifact,
    upsert_generated_artifact,
)
from tools.state_store_tools.invalidation import cascade_invalidation, detect_hash_changes
from tools.state_store_tools.invalidation_events import list_invalidation_events
from tools.state_store_tools.native_java_artifacts import (
    get_native_java_artifact,
    upsert_native_java_artifact,
)
from tools.state_store_tools.operation_closures import (
    get_operation_closure,
    upsert_operation_closure,
)
from tools.state_store_tools.process_locks import acquire_lock
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.service_layer_requirements import (
    get_service_layer_requirements,
    upsert_service_layer_requirements,
)
from tools.state_store_tools.source_artifacts import upsert_source_artifact


RUN_ID = "run-1"
CHANNEL = "INTERNET"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def seed_run(conn, auto_rerun: bool = True):
    upsert_run(
        conn,
        run_id=RUN_ID,
        run_mode="single_channel",
        run_config={"auto_rerun_impacted_operations": auto_rerun},
    )


def seed_operation_state(conn, operation_id: str):
    upsert_operation(
        conn,
        operation_id=operation_id,
        channel=CHANNEL,
        run_id=RUN_ID,
        xml_file_path=f"{operation_id}.xml",
        status="completed",
    )
    upsert_operation_closure(
        conn,
        operation_id=operation_id,
        channel=CHANNEL,
        run_id=RUN_ID,
        status="READY",
        closure={"operation_id": operation_id},
    )
    upsert_generated_artifact(
        conn,
        artifact_id=f"gen-{operation_id}",
        run_id=RUN_ID,
        operation_id=operation_id,
        channel=CHANNEL,
        target_language="java",
        artifact_kind="service",
        status="completed",
    )
    upsert_agent_task(
        conn,
        run_id=RUN_ID,
        agent_name="Agent",
        scope_type="operation",
        scope_id=operation_id,
        channel=CHANNEL,
        target_language="java",
        status="completed",
    )


def seed_hash_change(
    conn,
    *,
    artifact_id: str,
    kind: str,
    logical_id: str,
    operation_ids: list[str],
    shared: bool,
):
    for operation_id in operation_ids:
        seed_operation_state(conn, operation_id)
    upsert_source_artifact(
        conn,
        artifact_id=artifact_id,
        run_id=RUN_ID,
        kind=kind,
        logical_id=logical_id,
        source_hash="new-hash",
        shared=shared,
        used_by_ids=operation_ids,
    )
    upsert_native_java_artifact(
        conn,
        artifact_id=f"native-{logical_id}",
        run_id=RUN_ID,
        conversion_id=f"conv-{logical_id}",
        kind=kind,
        logical_id=logical_id,
        source_hash="old-hash",
        status="validated",
    )


def test_schema_creation_is_idempotent():
    conn = memory_conn()

    create_all_tables(conn)


def test_make_task_key_produces_expected_format():
    task_key = make_task_key(
        "run-1", "Agent", "operation", "GetClientLinks", "INTERNET", "java"
    )

    assert task_key == "run-1:Agent:operation:GetClientLinks:INTERNET:java:v1"


def test_reconcile_on_startup_resets_started_tasks_and_stale_locks():
    conn = memory_conn()
    seed_run(conn)
    task_id = upsert_agent_task(
        conn,
        run_id=RUN_ID,
        agent_name="Agent",
        scope_type="operation",
        scope_id="GetClientLinks",
        channel=CHANNEL,
        target_language="java",
        status="started",
    )
    assert acquire_lock(conn, task_id, RUN_ID)
    stale_time = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    conn.execute(
        "UPDATE process_locks SET heartbeat_at = ? WHERE task_id = ?",
        (stale_time, task_id),
    )
    conn.commit()

    reconcile_on_startup(conn, RUN_ID)

    assert get_agent_task(conn, task_id)["status"] == "needs_rerun"


def test_rule1_shared_impl_class_marks_dependent_records_stale():
    conn = memory_conn()
    seed_run(conn)
    seed_hash_change(
        conn,
        artifact_id="java-1",
        kind="ibm_java",
        logical_id="SharedImpl",
        operation_ids=["OpA", "OpB"],
        shared=True,
    )

    summary = cascade_invalidation(conn, RUN_ID, detect_hash_changes(conn, RUN_ID))

    assert summary.changed == 1
    assert get_native_java_artifact(conn, "native-SharedImpl")["status"] == "needs_rerun"
    assert get_generated_artifact(conn, "gen-OpA")["status"] == "needs_rerun"
    assert get_generated_artifact(conn, "gen-OpB")["status"] == "needs_rerun"
    assert get_operation(conn, "OpA", CHANNEL, RUN_ID)["status"] == "needs_rerun"
    assert len(list_invalidation_events(conn, RUN_ID)) == 1


def test_rule2_shared_format_marks_service_requirements_and_services_stale():
    conn = memory_conn()
    seed_run(conn)
    seed_hash_change(
        conn,
        artifact_id="fmt-1",
        kind="format",
        logical_id="SharedFormat",
        operation_ids=["OpA"],
        shared=True,
    )
    upsert_service_layer_requirements(
        conn,
        format_id="SharedFormat",
        channel=CHANNEL,
        run_id=RUN_ID,
        requirements={"format_id": "SharedFormat"},
        status="completed",
    )

    cascade_invalidation(conn, RUN_ID, detect_hash_changes(conn, RUN_ID))

    assert (
        get_service_layer_requirements(conn, "SharedFormat", CHANNEL, RUN_ID)["status"]
        == "needs_rerun"
    )
    assert get_generated_artifact(conn, "gen-OpA")["status"] == "needs_rerun"


def test_rule3_operation_xml_marks_only_that_operation_stale():
    conn = memory_conn()
    seed_run(conn)
    seed_hash_change(
        conn,
        artifact_id="op-xml-1",
        kind="operation",
        logical_id="OpA",
        operation_ids=[],
        shared=False,
    )
    seed_operation_state(conn, "OpA")
    seed_operation_state(conn, "OpB")

    cascade_invalidation(conn, RUN_ID, detect_hash_changes(conn, RUN_ID))

    assert get_generated_artifact(conn, "gen-OpA")["status"] == "needs_rerun"
    assert get_generated_artifact(conn, "gen-OpB")["status"] == "completed"


def test_rule4_context_marks_context_inventory_and_operations_stale():
    conn = memory_conn()
    seed_run(conn)
    seed_hash_change(
        conn,
        artifact_id="ctx-1",
        kind="context",
        logical_id="SharedContext",
        operation_ids=["OpA"],
        shared=True,
    )
    upsert_context_field_inventory(
        conn,
        context_id="SharedContext",
        channel=CHANNEL,
        run_id=RUN_ID,
        full_chain=["SharedContext"],
        inventory={"fields": []},
        status="completed",
    )

    cascade_invalidation(conn, RUN_ID, detect_hash_changes(conn, RUN_ID))

    assert (
        get_context_field_inventory(conn, "SharedContext", CHANNEL, RUN_ID)["status"]
        == "needs_rerun"
    )
    assert get_generated_artifact(conn, "gen-OpA")["status"] == "needs_rerun"


def test_rule5_local_artifact_marks_single_operation_chain_stale():
    conn = memory_conn()
    seed_run(conn)
    seed_hash_change(
        conn,
        artifact_id="local-step-1",
        kind="opStep",
        logical_id="LocalStep",
        operation_ids=["OpA"],
        shared=False,
    )
    seed_operation_state(conn, "OpB")

    cascade_invalidation(conn, RUN_ID, detect_hash_changes(conn, RUN_ID))

    assert get_generated_artifact(conn, "gen-OpA")["status"] == "needs_rerun"
    assert get_generated_artifact(conn, "gen-OpB")["status"] == "completed"


def test_auto_rerun_false_creates_event_without_marking_needs_rerun():
    conn = memory_conn()
    seed_run(conn, auto_rerun=False)
    seed_hash_change(
        conn,
        artifact_id="java-1",
        kind="ibm_java",
        logical_id="SharedImpl",
        operation_ids=["OpA"],
        shared=True,
    )

    summary = cascade_invalidation(conn, RUN_ID, detect_hash_changes(conn, RUN_ID))

    assert summary.paused is True
    assert len(list_invalidation_events(conn, RUN_ID)) == 1
    assert get_generated_artifact(conn, "gen-OpA")["status"] == "completed"
    assert get_native_java_artifact(conn, "native-SharedImpl")["status"] == "validated"
