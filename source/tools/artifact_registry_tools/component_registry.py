from __future__ import annotations

import sqlite3

from models.registry_models import ComponentRegistryRecord
from tools.state_store_tools._json import dumps, loads, utc_now


def register_component(conn: sqlite3.Connection, record: ComponentRegistryRecord) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO component_registry (
            component_id, run_id, artifact_kind, logical_id, source_hash,
            target_language, artifact_schema_version, generated_path, status,
            used_by_operations_json, used_by_validated_operations,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(component_id) DO UPDATE SET
            artifact_kind = excluded.artifact_kind,
            logical_id = excluded.logical_id,
            source_hash = excluded.source_hash,
            target_language = excluded.target_language,
            artifact_schema_version = excluded.artifact_schema_version,
            generated_path = excluded.generated_path,
            status = excluded.status,
            used_by_operations_json = excluded.used_by_operations_json,
            used_by_validated_operations = excluded.used_by_validated_operations,
            updated_at = excluded.updated_at
        """,
        (
            record.component_id,
            getattr(record, "run_id", "global"),
            record.artifact_kind,
            record.logical_id,
            record.source_hash,
            record.target_language.value,
            record.artifact_schema_version,
            record.generated_path,
            record.status.value,
            dumps(record.used_by_operations),
            record.used_by_validated_operations,
            now,
            now,
        ),
    )
    conn.commit()


def get_component(
    conn: sqlite3.Connection,
    artifact_kind: str,
    logical_id: str,
    target_language: str,
    schema_version: str,
) -> ComponentRegistryRecord | None:
    row = conn.execute(
        """
        SELECT * FROM component_registry
        WHERE artifact_kind = ?
          AND logical_id = ?
          AND target_language = ?
          AND artifact_schema_version = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (artifact_kind, logical_id, target_language, schema_version),
    ).fetchone()
    if row is None:
        return None
    return _record_from_row(row)


def get_component_by_id(conn: sqlite3.Connection, component_id: str) -> ComponentRegistryRecord | None:
    row = conn.execute(
        "SELECT * FROM component_registry WHERE component_id = ?", (component_id,)
    ).fetchone()
    if row is None:
        return None
    return _record_from_row(row)


def mark_validated(
    conn: sqlite3.Connection,
    component_id: str,
    *,
    common_lib_root: str | None = None,
    run_id: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE component_registry
        SET status = 'validated', updated_at = ?
        WHERE component_id = ?
        """,
        (utc_now(), component_id),
    )
    conn.commit()
    if common_lib_root and run_id:
        from tools.common_lib_tools.promotion import maybe_promote

        maybe_promote(conn, component_id, common_lib_root, run_id)


def increment_used_by_validated(conn: sqlite3.Connection, component_id: str) -> None:
    conn.execute(
        """
        UPDATE component_registry
        SET used_by_validated_operations = used_by_validated_operations + 1,
            updated_at = ?
        WHERE component_id = ?
        """,
        (utc_now(), component_id),
    )
    conn.commit()


def get_used_by_validated_count(conn: sqlite3.Connection, component_id: str) -> int:
    row = conn.execute(
        """
        SELECT used_by_validated_operations
        FROM component_registry
        WHERE component_id = ?
        """,
        (component_id,),
    ).fetchone()
    if row is None:
        return 0
    return int(row["used_by_validated_operations"])


def list_shared_candidates(
    conn: sqlite3.Connection, run_id: str, min_used_by: int = 2
) -> list[ComponentRegistryRecord]:
    rows = conn.execute(
        """
        SELECT * FROM component_registry
        WHERE run_id = ?
          AND used_by_validated_operations >= ?
        ORDER BY artifact_kind, logical_id
        """,
        (run_id, min_used_by),
    ).fetchall()
    return [_record_from_row(row) for row in rows]


def _record_from_row(row: sqlite3.Row) -> ComponentRegistryRecord:
    return ComponentRegistryRecord(
        component_id=row["component_id"],
        artifact_kind=row["artifact_kind"],
        logical_id=row["logical_id"],
        source_path="",
        source_hash=row["source_hash"] or "",
        target_language=row["target_language"],
        artifact_schema_version=row["artifact_schema_version"],
        generated_path=row["generated_path"] or "",
        status=row["status"],
        used_by_operations=loads(row["used_by_operations_json"], []) or [],
        used_by_validated_operations=int(row["used_by_validated_operations"]),
    )
