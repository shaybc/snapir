from __future__ import annotations

import sqlite3
from typing import Any

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def upsert_operation_closure(
    conn: sqlite3.Connection,
    *,
    operation_id: str,
    channel: str,
    run_id: str,
    status: str = "BLOCKED_UNRESOLVED_REFERENCE",
    closure: dict[str, Any] | None = None,
    blocking_issues: list[dict[str, Any]] | None = None,
    source_hash_composite: str | None = None,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO operation_closures (
            operation_id, channel, run_id, status, closure_json,
            blocking_issues_json, source_hash_composite, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(operation_id, channel, run_id) DO UPDATE SET
            status = excluded.status,
            closure_json = excluded.closure_json,
            blocking_issues_json = excluded.blocking_issues_json,
            source_hash_composite = excluded.source_hash_composite,
            updated_at = excluded.updated_at
        """,
        (
            operation_id,
            channel,
            run_id,
            status,
            dumps(closure),
            dumps(blocking_issues or []),
            source_hash_composite,
            now,
            now,
        ),
    )
    conn.commit()


def get_operation_closure(
    conn: sqlite3.Connection, operation_id: str, channel: str, run_id: str
) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM operation_closures
        WHERE operation_id = ? AND channel = ? AND run_id = ?
        """,
        (operation_id, channel, run_id),
    ).fetchone()
    return load_json_columns(row, ("closure_json", "blocking_issues_json"))
