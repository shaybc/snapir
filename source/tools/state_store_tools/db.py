from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from tools.state_store_tools._json import utc_now
from tools.state_store_tools.schema import SCHEMA_STATEMENTS

try:
    from constants import RUNNER_HEARTBEAT_TIMEOUT_SECONDS
except ImportError:
    RUNNER_HEARTBEAT_TIMEOUT_SECONDS = 300


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_all_tables(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.commit()
    from tools.state_store_tools.behavior_units import initialize
    initialize(conn)


def reconcile_on_startup(conn: sqlite3.Connection, run_id: str) -> None:
    cutoff = datetime.now(UTC) - timedelta(seconds=RUNNER_HEARTBEAT_TIMEOUT_SECONDS)
    cutoff_text = cutoff.isoformat()
    now = utc_now()
    stale_rows = conn.execute(
        """
        SELECT task_id FROM process_locks
        WHERE run_id = ? AND heartbeat_at < ?
        """,
        (run_id, cutoff_text),
    ).fetchall()
    stale_task_ids = [row["task_id"] for row in stale_rows]

    conn.execute(
        """
        UPDATE agent_tasks
        SET status = 'needs_rerun', updated_at = ?
        WHERE run_id = ? AND status = 'started'
        """,
        (now, run_id),
    )
    for task_id in stale_task_ids:
        conn.execute(
            """
            UPDATE agent_tasks
            SET status = 'needs_rerun', updated_at = ?
            WHERE run_id = ? AND task_id = ?
            """,
            (now, run_id, task_id),
        )
    conn.execute(
        """
        DELETE FROM process_locks
        WHERE run_id = ? AND heartbeat_at < ?
        """,
        (run_id, cutoff_text),
    )
    conn.commit()
