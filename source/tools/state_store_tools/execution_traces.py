from __future__ import annotations

import sqlite3
from typing import Any

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def insert_execution_trace(
    conn: sqlite3.Connection,
    *,
    trace_id: str,
    operation_id: str,
    channel: str,
    run_id: str,
    target: str,
    scenario: str,
    target_language: str | None = None,
    trace: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO execution_traces (
            trace_id, operation_id, channel, run_id, target, scenario,
            target_language, trace_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trace_id,
            operation_id,
            channel,
            run_id,
            target,
            scenario,
            target_language,
            dumps(trace),
            utc_now(),
        ),
    )
    conn.commit()


def get_execution_trace(conn: sqlite3.Connection, trace_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM execution_traces WHERE trace_id = ?", (trace_id,)).fetchone()
    return load_json_columns(row, ("trace_json",))
