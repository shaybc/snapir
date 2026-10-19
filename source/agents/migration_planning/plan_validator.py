from __future__ import annotations

import sqlite3

from models.common_models import RunConfig
from models.migration_models import MigrationPlan, OperationGrouping


def validate_migration_plan(
    plan: MigrationPlan,
    run_config: RunConfig,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    errors: list[str] = []
    operation_ids = _plan_operation_ids(plan)
    if plan.batches:
        pilot_size = len(plan.batches[0].task_packets)
        minimum = min(3, len(operation_ids), run_config.max_operations_per_batch)
        if pilot_size < minimum or pilot_size > 5:
            errors.append("Batch 1 size must be 3-5 operations")
    for batch in plan.batches:
        if len(batch.task_packets) > run_config.max_operations_per_batch:
            errors.append(f"Batch {batch.batch_id} exceeds MAX_OPERATIONS_PER_BATCH")

    identities = [(packet.operation_id, packet.channel) for batch in plan.batches for packet in batch.task_packets]
    duplicates = sorted({operation_id for operation_id, channel in identities if identities.count((operation_id, channel)) > 1})
    for operation_id in duplicates:
        errors.append(f"Operation appears more than once: {operation_id}")

    if conn is not None:
        from runtime.intake_plan import validate_dependency_order
        errors.extend(validate_dependency_order(conn, run_config.run_id, plan))
        expected = _operation_ids_from_db(conn, run_config.run_id)
        missing = sorted(expected - set(identities))
        extra = sorted(set(identities) - expected)
        for operation_id, channel in missing:
            errors.append(f"Plan is missing operation: {operation_id}")
        for operation_id, channel in extra:
            errors.append(f"Plan references unknown operation: {operation_id}")

    for index, batch in enumerate(plan.batches):
        unusual = [
            packet.operation_id
            for packet in batch.task_packets
            if packet.group == OperationGrouping.unusual_manual_review
        ]
        if unusual and index != len(plan.batches) - 1:
            errors.append("unusual_manual_review group must be in the final batch")
        if unusual and len(batch.task_packets) != len(unusual):
            errors.append("unusual_manual_review operations must be in their own batch")
    return errors


def _plan_operation_ids(plan: MigrationPlan) -> list[str]:
    return [
        packet.operation_id
        for batch in plan.batches
        for packet in batch.task_packets
    ]


def _operation_ids_from_db(conn: sqlite3.Connection, run_id: str) -> set[tuple[str, str]]:
    rows = conn.execute("SELECT operation_id, channel FROM operations WHERE run_id = ?", (run_id,)).fetchall()
    return {(row["operation_id"], row["channel"]) for row in rows}
