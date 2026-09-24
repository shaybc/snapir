from __future__ import annotations

import sqlite3

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def upsert_native_java_artifact(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    run_id: str,
    conversion_id: str,
    kind: str,
    logical_id: str,
    source_hash: str | None = None,
    artifact_path: str | None = None,
    compiles: bool = False,
    review_status: str = "pending",
    review_notes: list[str] | None = None,
    status: str = "pending",
    blocking_reason: str | None = None,
    attempt_number: int = 0,
    invalidation_event_id: str | None = None,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO native_java_artifacts (
            artifact_id, run_id, conversion_id, kind, logical_id, source_hash,
            invalidation_event_id, artifact_path, compiles, review_status,
            review_notes_json, status, blocking_reason, attempt_number,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(artifact_id) DO UPDATE SET
            source_hash = excluded.source_hash,
            invalidation_event_id = excluded.invalidation_event_id,
            artifact_path = excluded.artifact_path,
            compiles = excluded.compiles,
            review_status = excluded.review_status,
            review_notes_json = excluded.review_notes_json,
            status = excluded.status,
            blocking_reason = excluded.blocking_reason,
            attempt_number = excluded.attempt_number,
            updated_at = excluded.updated_at
        """,
        (
            artifact_id,
            run_id,
            conversion_id,
            kind,
            logical_id,
            source_hash,
            invalidation_event_id,
            artifact_path,
            int(compiles),
            review_status,
            dumps(review_notes or []),
            status,
            blocking_reason,
            attempt_number,
            now,
            now,
        ),
    )
    conn.commit()


def get_native_java_artifact(conn: sqlite3.Connection, artifact_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM native_java_artifacts WHERE artifact_id = ?", (artifact_id,)
    ).fetchone()
    return load_json_columns(row, ("review_notes_json",))
