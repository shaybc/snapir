from __future__ import annotations

import os
import socket
import sqlite3
from datetime import UTC, datetime, timedelta

from tools.state_store_tools._json import row_to_dict, utc_now

try:
    from constants import RUNNER_HEARTBEAT_TIMEOUT_SECONDS
except ImportError:
    RUNNER_HEARTBEAT_TIMEOUT_SECONDS = 300


def acquire_lock(
    conn: sqlite3.Connection,
    task_id: str,
    run_id: str,
    process_id: str | None = None,
    hostname: str | None = None,
) -> bool:
    now = utc_now()
    try:
        conn.execute(
            """
            INSERT INTO process_locks (
                task_id, run_id, process_id, hostname, started_at, heartbeat_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                run_id,
                process_id or str(os.getpid()),
                hostname or socket.gethostname(),
                now,
                now,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def release_lock(conn: sqlite3.Connection, task_id: str) -> None:
    conn.execute("DELETE FROM process_locks WHERE task_id = ?", (task_id,))
    conn.commit()


def heartbeat(conn: sqlite3.Connection, task_id: str) -> None:
    conn.execute(
        "UPDATE process_locks SET heartbeat_at = ? WHERE task_id = ?",
        (utc_now(), task_id),
    )
    conn.commit()


def get_lock(conn: sqlite3.Connection, task_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM process_locks WHERE task_id = ?", (task_id,)).fetchone()
    return row_to_dict(row)


def is_stale(lock: dict, timeout_seconds: int = RUNNER_HEARTBEAT_TIMEOUT_SECONDS) -> bool:
    heartbeat_at = datetime.fromisoformat(lock["heartbeat_at"])
    return heartbeat_at < datetime.now(UTC) - timedelta(seconds=timeout_seconds)
