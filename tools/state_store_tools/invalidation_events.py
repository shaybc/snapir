from __future__ import annotations

import sqlite3

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def insert_invalidation_event(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    run_id: str,
    corrected_artifact_id: str,
    corrected_artifact_kind: str,
    change_reason: str,
    old_hash: str | None = None,
    new_hash: str | None = None,
    affected_operation_ids: list[str] | None = None,
    affected_artifact_ids: list[str] | None = None,
    schema_version: str = "v1",
) -> None:
    conn.execute(
        """
        INSERT INTO invalidation_events (
            event_id, run_id, corrected_artifact_id, corrected_artifact_kind,
            change_reason, old_hash, new_hash, affected_operation_ids_json,
            affected_artifact_ids_json, created_at, schema_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            run_id,
            corrected_artifact_id,
            corrected_artifact_kind,
            change_reason,
            old_hash,
            new_hash,
            dumps(affected_operation_ids or []),
            dumps(affected_artifact_ids or []),
            utc_now(),
            schema_version,
        ),
    )


def get_invalidation_event(conn: sqlite3.Connection, event_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM invalidation_events WHERE event_id = ?", (event_id,)
    ).fetchone()
    return load_json_columns(row, ("affected_operation_ids_json", "affected_artifact_ids_json"))


def list_invalidation_events(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM invalidation_events
        WHERE run_id = ?
        ORDER BY created_at, event_id
        """,
        (run_id,),
    ).fetchall()
    return [
        load_json_columns(row, ("affected_operation_ids_json", "affected_artifact_ids_json"))
        for row in rows
    ]
