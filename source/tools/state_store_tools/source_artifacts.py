from __future__ import annotations

import sqlite3
from typing import Any

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def upsert_source_artifact(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    run_id: str,
    kind: str,
    logical_id: str,
    source_path: str | None = None,
    source_hash: str | None = None,
    channel: str | None = None,
    shared: bool = False,
    used_by_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    conversion_status: str = "not_started",
) -> None:
    now = utc_now()
    used_by_ids = used_by_ids or []
    conn.execute(
        """
        INSERT INTO source_artifacts (
            artifact_id, run_id, kind, logical_id, source_path, source_hash,
            channel, shared, used_by_count, used_by_ids_json, metadata_json,
            conversion_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(artifact_id) DO UPDATE SET
            kind = excluded.kind,
            logical_id = excluded.logical_id,
            source_path = excluded.source_path,
            source_hash = excluded.source_hash,
            channel = excluded.channel,
            shared = excluded.shared,
            used_by_count = excluded.used_by_count,
            used_by_ids_json = excluded.used_by_ids_json,
            metadata_json = excluded.metadata_json,
            conversion_status = excluded.conversion_status,
            updated_at = excluded.updated_at
        """,
        (
            artifact_id,
            run_id,
            kind,
            logical_id,
            source_path,
            source_hash,
            channel,
            int(shared),
            len(used_by_ids),
            dumps(used_by_ids),
            dumps(metadata),
            conversion_status,
            now,
            now,
        ),
    )
    conn.commit()


def get_source_artifact(conn: sqlite3.Connection, artifact_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM source_artifacts WHERE artifact_id = ?", (artifact_id,)
    ).fetchone()
    return load_json_columns(row, ("used_by_ids_json", "metadata_json"))


def list_source_artifacts(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM source_artifacts WHERE run_id = ? ORDER BY artifact_id", (run_id,)
    ).fetchall()
    return [load_json_columns(row, ("used_by_ids_json", "metadata_json")) for row in rows]
