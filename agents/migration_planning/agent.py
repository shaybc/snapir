from __future__ import annotations

import sqlite3
from collections import Counter

from models.common_models import RunConfig
from models.migration_models import MigrationPlan
from tools.state_store_tools._json import dumps, loads, utc_now

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

from constants import AGENT_MODEL


PLANNING_INSTRUCTION = """
You are a migration planner for the Composer Sunset pipeline.

Your job is to group WSBCC operations into batches for conversion.
You receive a list of operations with their complexity indicators
and must assign each to a group and a batch.

GROUPS (assign exactly one per operation):
- one_step: single opStep, no branching
- multi_step_linear: multiple opSteps, linear routing only
- branch_heavy: 3+ RC branches, complex routing graph
- db_bound: implClass is a stored procedure caller (db_accessor behavior type)
- shared_format_context: shares formats or context with many other operations
- unusual_manual_review: circular context, blocked closure, unusual patterns

BATCHING RULES:
- MAX_OPERATIONS_PER_BATCH = {max_ops_per_batch}
- Pilot batch (batch 1): 3-5 operations maximum. Include at least one from
  each group that is represented in the full set.
- Subsequent batches: up to MAX_OPERATIONS_PER_BATCH operations.
- unusual_manual_review group: always in its own batch, last.
- Prefer operations that share formats/contexts in the same batch to
  maximise common-lib reuse.

OUTPUT FORMAT: JSON matching the MigrationPlan schema.
Return only JSON, no explanation.
"""


migration_planning_agent = LlmAgent(
    name="MigrationPlanningAgent",
    description="Groups operations into batches by complexity.",
    model=AGENT_MODEL,
    instruction=PLANNING_INSTRUCTION,
    tools=[],
)


def get_operations_for_planning(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT operation_id, channel
        FROM operations
        WHERE run_id = ?
        ORDER BY operation_id, channel
        """,
        (run_id,),
    ).fetchall()
    return [
        _operation_indicators(conn, run_id, row["operation_id"], row["channel"])
        for row in rows
    ]


def write_migration_plan(conn: sqlite3.Connection, plan: MigrationPlan) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO migration_plans (
            plan_id, run_id, plan_json, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(plan_id) DO UPDATE SET
            plan_json = excluded.plan_json,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (
            plan.plan_id,
            plan.run_id,
            plan.model_dump_json(),
            plan.status.value,
            now,
            now,
        ),
    )
    conn.commit()


def build_gate1_report(
    plan: MigrationPlan,
    run_config: RunConfig,
    planning_operations: list[dict],
) -> str:
    operation_ids = [
        packet.operation_id
        for batch in plan.batches
        for packet in batch.task_packets
    ]
    pilot_ids = [packet.operation_id for packet in plan.batches[0].task_packets] if plan.batches else []
    groups = Counter(
        packet.group.value
        for batch in plan.batches
        for packet in batch.task_packets
    )
    shared_formats = sum(item["shared_formats_count"] for item in planning_operations)
    blocked = sum(1 for item in planning_operations if item["has_blocked_context"])
    group_text = ", ".join(f"{group}={groups.get(group, 0)}" for group in sorted(groups))
    return "\n".join(
        [
            "=== Human Gate 1 ===",
            f"Operations to migrate: {len(operation_ids)}",
            f"Pilot batch: {pilot_ids}",
            f"Batches planned: {len(plan.batches)}",
            f"Groups: {group_text}",
            f"Shared formats: {shared_formats}",
            f"Blocked (needs_human_review): {blocked}",
            f"INCLUDE_OPERATIONS filter active: {'yes' if run_config.include_operations else 'no'}",
            f"EXCLUDE_OPERATIONS filter active: {'yes' if run_config.exclude_operations else 'no'}",
            "",
            "Approve pilot batch? (yes/no)",
        ]
    )


def _operation_indicators(
    conn: sqlite3.Connection, run_id: str, operation_id: str, channel: str
) -> dict:
    operation_artifact = _source_artifact(conn, run_id, "operation", operation_id)
    metadata = loads(operation_artifact["metadata_json"], {}) if operation_artifact else {}
    steps = metadata.get("steps", [])
    step_count = len(steps)
    branch_values = set()
    behavior_types = set()
    shared_classes_count = 0
    for step_id in steps:
        step_artifact = _source_artifact(conn, run_id, "opStep", step_id)
        step_metadata = loads(step_artifact["metadata_json"], {}) if step_artifact else {}
        branch_values.update((step_metadata.get("transitions") or {}).keys())
        impl_class = step_metadata.get("impl_class")
        if impl_class:
            class_artifact = _source_artifact(conn, run_id, "java_class", impl_class)
            class_metadata = loads(class_artifact["metadata_json"], {}) if class_artifact else {}
            behavior_types.update(class_metadata.get("behavior_types", []))
            if class_artifact and class_artifact["shared"]:
                shared_classes_count += 1
    ref_formats = metadata.get("ref_formats", {}) or {}
    shared_formats_count = sum(
        1
        for format_id in ref_formats.values()
        if _artifact_is_shared(_source_artifact(conn, run_id, "format", format_id))
    )
    has_blocked_context = _has_blocked_context(conn, run_id, metadata.get("operation_context"))
    return {
        "operation_id": operation_id,
        "channel": channel,
        "step_count": step_count,
        "branch_count": len(branch_values),
        "shared_formats_count": shared_formats_count,
        "shared_classes_count": shared_classes_count,
        "behavior_types": sorted(behavior_types),
        "has_blocked_context": has_blocked_context,
    }


def _source_artifact(conn: sqlite3.Connection, run_id: str, kind: str, logical_id: str):
    return conn.execute(
        """
        SELECT * FROM source_artifacts
        WHERE run_id = ? AND kind = ? AND logical_id = ?
        """,
        (run_id, kind, logical_id),
    ).fetchone()


def _artifact_is_shared(row) -> bool:
    return bool(row and row["shared"])


def _has_blocked_context(conn: sqlite3.Connection, run_id: str, context_id: str | None) -> bool:
    if not context_id:
        return False
    row = conn.execute(
        """
        SELECT has_cycle FROM context_hierarchies
        WHERE run_id = ? AND context_id = ?
        """,
        (run_id, context_id),
    ).fetchone()
    return bool(row and row["has_cycle"])
