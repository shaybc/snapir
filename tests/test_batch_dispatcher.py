from __future__ import annotations

import threading
import time

from models.common_models import RunConfig, RunMode, TargetLanguage, TaskStatus
from models.conversion_models import ConversionStatus
from models.migration_models import MigrationBatch, MigrationPlan, MigrationTaskPacket, OperationGrouping
from models.registry_models import ComponentRegistryRecord
from tools.artifact_registry_tools.component_registry import register_component
from tools.routing_tools.batch_dispatcher import dispatch_all_batches, dispatch_batch
from tools.routing_tools.batch_progress_tracker import get_batch_progress, update_progress
from tools.state_store_tools.db import create_all_tables, get_connection


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def run_config(max_conversion_workers: int = 2) -> RunConfig:
    return RunConfig(
        run_id=RUN_ID,
        run_mode=RunMode.single_channel,
        source_root="input",
        vault_root="vault",
        output_root="generated",
        db_path="state.db",
        target_channels=["INTERNET"],
        target_languages=[TargetLanguage.java],
        enable_git=False,
        artifact_schema_version="v1",
        max_agent_task_retries=3,
        max_parallel_conversion_workers=max_conversion_workers,
        max_parallel_llm_tasks=1,
        max_parallel_build_tasks=2,
        max_operations_per_batch=5,
        model_name="test",
        model_base_url="",
        auto_rerun_impacted_operations=True,
    )


def packet(operation_id: str) -> MigrationTaskPacket:
    return MigrationTaskPacket(
        task_id=f"task-{operation_id}",
        run_id=RUN_ID,
        operation_id=operation_id,
        channel="INTERNET",
        target_language=TargetLanguage.java,
        group=OperationGrouping.one_step,
        status=TaskStatus.pending,
    )


def batch(*operation_ids: str) -> MigrationBatch:
    return MigrationBatch(
        batch_id="batch-1",
        run_id=RUN_ID,
        task_packets=[packet(operation_id) for operation_id in operation_ids],
        is_pilot=True,
        status=TaskStatus.pending,
    )


def test_dispatch_batch_respects_max_parallel_conversion_workers_limit():
    conn = memory_conn()
    active = 0
    max_seen = 0
    lock = threading.Lock()

    def conversion(conn, packet, config):
        nonlocal active, max_seen
        with lock:
            active += 1
            max_seen = max(max_seen, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return "completed"

    dispatch_batch(
        conn,
        batch("OpA", "OpB", "OpC", "OpD"),
        run_config(max_conversion_workers=2),
        lambda operation_id: None,
        lambda operation_id, reason: None,
        phase_handlers={"conversion": conversion},
    )

    assert max_seen <= 2


def test_blocked_operation_in_batch_does_not_prevent_other_completions():
    conn = memory_conn()
    completed = []
    failed = []

    def closure(conn, packet, config):
        if packet.operation_id == "OpA":
            return "blocked", "missing_implclass_source"
        return "completed"

    result = dispatch_batch(
        conn,
        batch("OpA", "OpB"),
        run_config(),
        completed.append,
        lambda operation_id, reason: failed.append((operation_id, reason)),
        phase_handlers={"closure": closure},
    )

    assert result.blocked_count == 1
    assert result.success_count == 1
    assert completed == ["OpB"]
    assert failed == [("OpA", "missing_implclass_source")]


def test_progress_tracker_shows_correct_fraction_after_completion(capsys):
    conn = memory_conn()
    update_progress(conn, RUN_ID, "batch-1", "OpA", "completed")
    update_progress(conn, RUN_ID, "batch-1", "OpB", "pending")

    progress = get_batch_progress(conn, RUN_ID, "batch-1")

    assert progress["completed"] == 1
    assert progress["pending"] == 1


def test_common_lib_rebuild_triggered_after_batch_with_shared_promotions():
    conn = memory_conn()
    register_component(
        conn,
        ComponentRegistryRecord(
            component_id="component-1",
            artifact_kind="ibm_java",
            logical_id="SharedStep",
            source_path="",
            source_hash="hash",
            target_language=TargetLanguage.java,
            artifact_schema_version="v1",
            generated_path="common-lib/SharedStep.java",
            status=ConversionStatus.validated,
            used_by_operations=["OpA", "OpB"],
            used_by_validated_operations=2,
        ),
    )
    plan = MigrationPlan(
        plan_id="plan-1",
        run_id=RUN_ID,
        batches=[batch("OpA")],
        total_operations=1,
        unusual_count=0,
        status=TaskStatus.pending,
    )
    rebuilds = []

    result = dispatch_all_batches(
        conn,
        plan,
        run_config(),
        common_lib_rebuilder=lambda conn, run_id: rebuilds.append(run_id) or True,
    )

    assert rebuilds == [RUN_ID]
    assert result.common_lib_rebuilds == 1
