from __future__ import annotations

from models.common_models import RunConfig, RunMode, TargetLanguage, TaskStatus
from models.migration_models import (
    MigrationBatch,
    MigrationPlan,
    MigrationTaskPacket,
    OperationGrouping,
)
from agents.migration_planning.agent import build_gate1_report
from agents.migration_planning.plan_validator import validate_migration_plan
from tools.state_store_tools.channel_operations import upsert_operation
from tools.state_store_tools.db import create_all_tables, get_connection


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def run_config(*, include=None, exclude=None, max_ops=5):
    return RunConfig(
        run_id=RUN_ID,
        run_mode=RunMode.single_channel,
        source_root="composer",
        vault_root="vault",
        output_root="out",
        db_path="state.db",
        target_channels=["INTERNET"],
        composer_mapper_channel_filter="INTERNET",
        target_languages=[TargetLanguage.java],
        enable_git=False,
        artifact_schema_version="v1",
        max_agent_task_retries=3,
        max_parallel_conversion_workers=4,
        max_parallel_llm_tasks=2,
        max_parallel_build_tasks=2,
        max_operations_per_batch=max_ops,
        model_name="model",
        model_base_url="http://localhost",
        auto_rerun_impacted_operations=True,
        include_operations=include,
        exclude_operations=exclude,
    )


def packet(operation_id: str, group=OperationGrouping.one_step):
    return MigrationTaskPacket(
        task_id=f"task-{operation_id}",
        run_id=RUN_ID,
        operation_id=operation_id,
        channel="INTERNET",
        target_language=TargetLanguage.java,
        group=group,
        status=TaskStatus.pending,
    )


def plan(batches):
    return MigrationPlan(
        plan_id="plan-1",
        run_id=RUN_ID,
        batches=batches,
        total_operations=sum(len(batch.task_packets) for batch in batches),
        unusual_count=sum(
            1
            for batch in batches
            for task_packet in batch.task_packets
            if task_packet.group == OperationGrouping.unusual_manual_review
        ),
        status=TaskStatus.pending,
    )


def batch(batch_id: str, packets, is_pilot=False):
    return MigrationBatch(
        batch_id=batch_id,
        run_id=RUN_ID,
        task_packets=packets,
        is_pilot=is_pilot,
        status=TaskStatus.pending,
    )


def seed_operations(conn, operation_ids):
    for operation_id in operation_ids:
        upsert_operation(
            conn,
            operation_id=operation_id,
            channel="INTERNET",
            run_id=RUN_ID,
            xml_file_path=f"{operation_id}.xml",
        )


def test_validator_rejects_batch_1_with_six_operations():
    migration_plan = plan([
        batch("batch-1", [packet(f"Op{i}") for i in range(6)], is_pilot=True)
    ])

    errors = validate_migration_plan(migration_plan, run_config())

    assert "Batch 1 size must be 3-5 operations" in errors


def test_validator_rejects_plan_missing_operation():
    conn = memory_conn()
    seed_operations(conn, ["OpA", "OpB", "OpC"])
    migration_plan = plan([
        batch("batch-1", [packet("OpA"), packet("OpB"), packet("OpD")], is_pilot=True)
    ])

    errors = validate_migration_plan(migration_plan, run_config(), conn)

    assert "Plan is missing operation: OpC" in errors
    assert "Plan references unknown operation: OpD" in errors


def test_validator_rejects_unusual_manual_review_in_non_final_batch():
    migration_plan = plan([
        batch("batch-1", [
            packet("OpA"),
            packet("OpB"),
            packet("OpC", OperationGrouping.unusual_manual_review),
        ], is_pilot=True),
        batch("batch-2", [packet("OpD")]),
    ])

    errors = validate_migration_plan(migration_plan, run_config())

    assert "unusual_manual_review group must be in the final batch" in errors
    assert "unusual_manual_review operations must be in their own batch" in errors


def test_gate1_report_includes_include_exclude_filter_status():
    migration_plan = plan([
        batch("batch-1", [packet("OpA"), packet("OpB"), packet("OpC")], is_pilot=True)
    ])

    report = build_gate1_report(
        migration_plan,
        run_config(include=["OpA"], exclude=["OpZ"]),
        planning_operations=[
            {
                "operation_id": "OpA",
                "shared_formats_count": 1,
                "has_blocked_context": False,
            },
            {
                "operation_id": "OpB",
                "shared_formats_count": 0,
                "has_blocked_context": True,
            },
            {
                "operation_id": "OpC",
                "shared_formats_count": 0,
                "has_blocked_context": False,
            },
        ],
    )

    assert "INCLUDE_OPERATIONS filter active: yes" in report
    assert "EXCLUDE_OPERATIONS filter active: yes" in report
    assert "Blocked (needs_human_review): 1" in report


def test_validator_accepts_small_scope():
    conn = memory_conn()
    seed_operations(conn, ["OpA"])
    migration_plan = plan([batch("batch-1", [packet("OpA")], is_pilot=True)])
    assert validate_migration_plan(migration_plan, run_config(), conn) == []


def test_validator_preserves_channel_identity():
    conn = memory_conn()
    seed_operations(conn, ["OpA"])
    upsert_operation(conn, operation_id="OpA", channel="IVR", run_id=RUN_ID, xml_file_path="ivr.xml")
    other = packet("OpA").model_copy(update={"channel": "IVR", "task_id": "ivr-task"})
    migration_plan = plan([batch("batch-1", [packet("OpA"), other], is_pilot=True)])
    assert validate_migration_plan(migration_plan, run_config(), conn) == []
