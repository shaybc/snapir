from __future__ import annotations

import sqlite3

from tools.state_store_tools._json import row_to_dict, utc_now


def upsert_generated_artifact(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    run_id: str,
    operation_id: str,
    channel: str,
    target_language: str,
    artifact_kind: str,
    source_hash: str | None = None,
    generated_path: str | None = None,
    status: str = "pending",
    blocking_reason: str | None = None,
    attempt_number: int = 0,
    artifact_schema_version: str = "v1",
    invalidation_event_id: str | None = None,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO generated_artifacts (
            artifact_id, run_id, operation_id, channel, target_language,
            artifact_kind, source_hash, invalidation_event_id,
            artifact_schema_version, generated_path, status, blocking_reason,
            attempt_number, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(artifact_id) DO UPDATE SET
            source_hash = excluded.source_hash,
            invalidation_event_id = excluded.invalidation_event_id,
            generated_path = excluded.generated_path,
            status = excluded.status,
            blocking_reason = excluded.blocking_reason,
            attempt_number = excluded.attempt_number,
            updated_at = excluded.updated_at
        """,
        (
            artifact_id,
            run_id,
            operation_id,
            channel,
            target_language,
            artifact_kind,
            source_hash,
            invalidation_event_id,
            artifact_schema_version,
            generated_path,
            status,
            blocking_reason,
            attempt_number,
            now,
            now,
        ),
    )
    conn.commit()


def get_generated_artifact(conn: sqlite3.Connection, artifact_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM generated_artifacts WHERE artifact_id = ?", (artifact_id,)
    ).fetchone()
    return row_to_dict(row)
