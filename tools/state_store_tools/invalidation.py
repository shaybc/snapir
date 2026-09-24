from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

from tools.state_store_tools._json import loads, placeholders, utc_now
from tools.state_store_tools.invalidation_events import insert_invalidation_event


@dataclass(frozen=True)
class HashChange:
    artifact_id: str
    artifact_kind: str
    logical_id: str
    old_hash: str | None
    new_hash: str | None
    shared: bool = False
    affected_operation_ids: list[str] = field(default_factory=list)


@dataclass
class InvalidationSummary:
    changed: int = 0
    stale_conversions: int = 0
    stale_operations: int = 0
    stale_services: int = 0
    invalidation_event_ids: list[str] = field(default_factory=list)
    paused: bool = False


def detect_hash_changes(conn: sqlite3.Connection, run_id: str) -> list[HashChange]:
    changes: list[HashChange] = []
    rows = conn.execute(
        """
        SELECT * FROM source_artifacts
        WHERE run_id = ? AND source_hash IS NOT NULL
        """,
        (run_id,),
    ).fetchall()
    for row in rows:
        old_hash = _find_existing_hash(conn, run_id, row["logical_id"])
        if old_hash is not None and old_hash != row["source_hash"]:
            changes.append(
                HashChange(
                    artifact_id=row["artifact_id"],
                    artifact_kind=row["kind"],
                    logical_id=row["logical_id"],
                    old_hash=old_hash,
                    new_hash=row["source_hash"],
                    shared=bool(row["shared"]),
                    affected_operation_ids=loads(row["used_by_ids_json"], []) or [],
                )
            )
    return changes


def cascade_invalidation(
    conn: sqlite3.Connection, run_id: str, changes: list[HashChange]
) -> InvalidationSummary:
    summary = InvalidationSummary(changed=len(changes), paused=not _auto_rerun(conn, run_id))
    for change in changes:
        with conn:
            affected_operations = _affected_operations(change)
            affected_artifacts = _matching_artifact_ids(conn, run_id, change, affected_operations)
            event_id = f"inv-{uuid.uuid4()}"
            insert_invalidation_event(
                conn,
                event_id=event_id,
                run_id=run_id,
                corrected_artifact_id=change.artifact_id,
                corrected_artifact_kind=change.artifact_kind,
                change_reason="hash_mismatch",
                old_hash=change.old_hash,
                new_hash=change.new_hash,
                affected_operation_ids=affected_operations,
                affected_artifact_ids=affected_artifacts,
            )
            summary.invalidation_event_ids.append(event_id)
            if summary.paused:
                continue

            if _is_shared_impl_class(change):
                counts = _rule1_shared_impl_class(conn, change, run_id)
            elif _is_shared_format(change):
                counts = _rule2_shared_format(conn, change, run_id)
            elif _is_operation(change):
                counts = _rule3_operation_xml(conn, change, run_id)
            elif _is_context(change):
                counts = _rule4_context(conn, change, run_id)
            else:
                counts = _rule5_local_artifact(conn, change, run_id)

            summary.stale_conversions += counts["conversions"]
            summary.stale_operations += counts["operations"]
            summary.stale_services += counts["services"]
    return summary


def _rule1_shared_impl_class(
    conn: sqlite3.Connection, change: HashChange, run_id: str
) -> dict[str, int]:
    affected_operations = _affected_operations(change)
    conversions = _mark_native_java_stale(conn, run_id, change.logical_id)
    services = _mark_generated_for_operations_stale(conn, run_id, affected_operations)
    operations = _mark_operation_records_stale(conn, run_id, affected_operations)
    _mark_tasks_stale(conn, run_id, affected_operations + [change.logical_id])
    _mark_component_registry_stale(conn, run_id, change.logical_id, affected_operations)
    return {"conversions": conversions, "operations": operations, "services": services}


def _rule2_shared_format(conn: sqlite3.Connection, change: HashChange, run_id: str) -> dict[str, int]:
    affected_operations = _affected_operations(change)
    conversions = _mark_native_java_stale(conn, run_id, change.logical_id)
    conversions += _mark_service_layer_requirements_stale(conn, run_id, change.logical_id)
    services = _mark_generated_for_operations_stale(conn, run_id, affected_operations)
    operations = _mark_operation_records_stale(conn, run_id, affected_operations)
    _mark_tasks_stale(conn, run_id, affected_operations + [change.logical_id])
    _mark_component_registry_stale(conn, run_id, change.logical_id, affected_operations)
    return {"conversions": conversions, "operations": operations, "services": services}


def _rule3_operation_xml(conn: sqlite3.Connection, change: HashChange, run_id: str) -> dict[str, int]:
    affected_operations = _affected_operations(change) or [change.logical_id]
    conversions = _mark_native_java_stale(conn, run_id, change.logical_id)
    services = _mark_generated_for_operations_stale(conn, run_id, affected_operations)
    operations = _mark_operation_records_stale(conn, run_id, affected_operations)
    _mark_tasks_stale(conn, run_id, affected_operations)
    return {"conversions": conversions, "operations": operations, "services": services}


def _rule4_context(conn: sqlite3.Connection, change: HashChange, run_id: str) -> dict[str, int]:
    affected_operations = _affected_operations(change)
    conversions = _mark_context_records_stale(conn, run_id, change.logical_id)
    services = _mark_generated_for_operations_stale(conn, run_id, affected_operations)
    operations = _mark_operation_records_stale(conn, run_id, affected_operations)
    _mark_tasks_stale(conn, run_id, affected_operations + [change.logical_id])
    return {"conversions": conversions, "operations": operations, "services": services}


def _rule5_local_artifact(conn: sqlite3.Connection, change: HashChange, run_id: str) -> dict[str, int]:
    affected_operations = _affected_operations(change)
    conversions = _mark_native_java_stale(conn, run_id, change.logical_id)
    services = _mark_generated_for_operations_stale(conn, run_id, affected_operations)
    operations = _mark_operation_records_stale(conn, run_id, affected_operations)
    _mark_tasks_stale(conn, run_id, affected_operations + [change.logical_id])
    return {"conversions": conversions, "operations": operations, "services": services}


def _find_existing_hash(conn: sqlite3.Connection, run_id: str, logical_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT source_hash FROM native_java_artifacts
        WHERE run_id = ? AND logical_id = ? AND source_hash IS NOT NULL
        UNION
        SELECT source_hash FROM component_registry
        WHERE run_id = ? AND logical_id = ? AND source_hash IS NOT NULL
        LIMIT 1
        """,
        (run_id, logical_id, run_id, logical_id),
    ).fetchone()
    return None if row is None else row["source_hash"]


def _auto_rerun(conn: sqlite3.Connection, run_id: str) -> bool:
    row = conn.execute("SELECT run_config_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None or row["run_config_json"] is None:
        return True
    config = loads(row["run_config_json"], {}) or {}
    return bool(config.get("auto_rerun_impacted_operations", True))


def _affected_operations(change: HashChange) -> list[str]:
    if change.affected_operation_ids:
        return list(dict.fromkeys(change.affected_operation_ids))
    if _is_operation(change):
        return [change.logical_id]
    return []


def _matching_artifact_ids(
    conn: sqlite3.Connection, run_id: str, change: HashChange, operation_ids: list[str]
) -> list[str]:
    artifact_ids: list[str] = []
    rows = conn.execute(
        """
        SELECT artifact_id FROM native_java_artifacts
        WHERE run_id = ? AND logical_id = ?
        """,
        (run_id, change.logical_id),
    ).fetchall()
    artifact_ids.extend(row["artifact_id"] for row in rows)
    if operation_ids:
        sql = (
            "SELECT artifact_id FROM generated_artifacts "
            f"WHERE run_id = ? AND operation_id IN ({placeholders(operation_ids)})"
        )
        rows = conn.execute(sql, [run_id, *operation_ids]).fetchall()
        artifact_ids.extend(row["artifact_id"] for row in rows)
    return list(dict.fromkeys(artifact_ids))


def _mark_native_java_stale(conn: sqlite3.Connection, run_id: str, logical_id: str) -> int:
    cur = conn.execute(
        """
        UPDATE native_java_artifacts
        SET status = 'needs_rerun', updated_at = ?
        WHERE run_id = ? AND logical_id = ?
        """,
        (utc_now(), run_id, logical_id),
    )
    return cur.rowcount


def _mark_service_layer_requirements_stale(
    conn: sqlite3.Connection, run_id: str, format_id: str
) -> int:
    cur = conn.execute(
        """
        UPDATE service_layer_requirements
        SET status = 'needs_rerun', updated_at = ?
        WHERE run_id = ? AND format_id = ?
        """,
        (utc_now(), run_id, format_id),
    )
    return cur.rowcount


def _mark_context_records_stale(conn: sqlite3.Connection, run_id: str, context_id: str) -> int:
    now = utc_now()
    cur = conn.execute(
        """
        UPDATE context_field_inventories
        SET status = 'needs_rerun', updated_at = ?
        WHERE run_id = ? AND (
            context_id = ? OR full_chain_json LIKE ?
        )
        """,
        (now, run_id, context_id, f'%"{context_id}"%'),
    )
    conn.execute("DELETE FROM context_hierarchies WHERE run_id = ? AND context_id = ?", (run_id, context_id))
    return cur.rowcount


def _mark_generated_for_operations_stale(
    conn: sqlite3.Connection, run_id: str, operation_ids: list[str]
) -> int:
    if not operation_ids:
        return 0
    sql = (
        "UPDATE generated_artifacts SET status = 'needs_rerun', updated_at = ? "
        f"WHERE run_id = ? AND operation_id IN ({placeholders(operation_ids)})"
    )
    cur = conn.execute(sql, [utc_now(), run_id, *operation_ids])
    return cur.rowcount


def _mark_operation_records_stale(
    conn: sqlite3.Connection, run_id: str, operation_ids: list[str]
) -> int:
    if not operation_ids:
        return 0
    total = 0
    now = utc_now()
    for table in ("operations", "operation_closures", "routing_plans", "context_plans", "serialization_plans"):
        id_column = "operation_id"
        sql = (
            f"UPDATE {table} SET status = 'needs_rerun', updated_at = ? "
            f"WHERE run_id = ? AND {id_column} IN ({placeholders(operation_ids)})"
        )
        total += conn.execute(sql, [now, run_id, *operation_ids]).rowcount
    return total


def _mark_tasks_stale(conn: sqlite3.Connection, run_id: str, scope_ids: list[str]) -> int:
    if not scope_ids:
        return 0
    sql = (
        "UPDATE agent_tasks SET status = 'needs_rerun', updated_at = ? "
        f"WHERE run_id = ? AND scope_id IN ({placeholders(scope_ids)})"
    )
    return conn.execute(sql, [utc_now(), run_id, *scope_ids]).rowcount


def _mark_component_registry_stale(
    conn: sqlite3.Connection, run_id: str, logical_id: str, operation_ids: list[str]
) -> int:
    total = conn.execute(
        """
        UPDATE component_registry
        SET status = 'needs_rerun', updated_at = ?
        WHERE run_id = ? AND logical_id = ?
        """,
        (utc_now(), run_id, logical_id),
    ).rowcount
    for operation_id in operation_ids:
        total += conn.execute(
            """
            UPDATE component_registry
            SET status = 'needs_rerun', updated_at = ?
            WHERE run_id = ? AND used_by_operations_json LIKE ?
            """,
            (utc_now(), run_id, f'%"{operation_id}"%'),
        ).rowcount
    return total


def _is_shared_impl_class(change: HashChange) -> bool:
    return change.shared and change.artifact_kind in {
        "java",
        "java_class",
        "impl_class",
        "ibm_java",
    }


def _is_shared_format(change: HashChange) -> bool:
    return change.shared and change.artifact_kind in {"format", "xml_fmtdef", "fmtdef"}


def _is_operation(change: HashChange) -> bool:
    return change.artifact_kind in {"operation", "xml_operation", "operation_xml"}


def _is_context(change: HashChange) -> bool:
    return change.artifact_kind in {"context", "xml_context"}
