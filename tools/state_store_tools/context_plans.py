from __future__ import annotations

import sqlite3
from typing import Any

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def upsert_context_plan(
    conn: sqlite3.Connection,
    *,
    operation_id: str,
    channel: str,
    run_id: str,
    plan: dict[str, Any] | None = None,
    status: str = "pending",
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO context_plans (
            operation_id, channel, run_id, plan_json, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(operation_id, channel, run_id) DO UPDATE SET
            plan_json = excluded.plan_json,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (operation_id, channel, run_id, dumps(plan), status, now, now),
    )
    conn.commit()


def get_context_plan(
    conn: sqlite3.Connection, operation_id: str, channel: str, run_id: str
) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM context_plans
        WHERE operation_id = ? AND channel = ? AND run_id = ?
        """,
        (operation_id, channel, run_id),
    ).fetchone()
    return load_json_columns(row, ("plan_json",))
