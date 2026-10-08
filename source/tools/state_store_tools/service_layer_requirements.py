from __future__ import annotations

import sqlite3
from typing import Any

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def upsert_service_layer_requirements(
    conn: sqlite3.Connection,
    *,
    format_id: str,
    channel: str,
    run_id: str,
    requirements: dict[str, Any] | None = None,
    status: str = "pending",
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO service_layer_requirements (
            format_id, channel, run_id, requirements_json, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(format_id, channel, run_id) DO UPDATE SET
            requirements_json = excluded.requirements_json,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (format_id, channel, run_id, dumps(requirements), status, now, now),
    )
    conn.commit()


def get_service_layer_requirements(
    conn: sqlite3.Connection, format_id: str, channel: str, run_id: str
) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM service_layer_requirements
        WHERE format_id = ? AND channel = ? AND run_id = ?
        """,
        (format_id, channel, run_id),
    ).fetchone()
    return load_json_columns(row, ("requirements_json",))
