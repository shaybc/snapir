from __future__ import annotations

import sqlite3

from tools.state_store_tools.agent_tasks import upsert_agent_task


def update_progress(
    conn: sqlite3.Connection,
    run_id: str,
    batch_id: str,
    operation_id: str,
    status: str,
) -> None:
    """Persist progress for one operation in one batch."""
    upsert_agent_task(
        conn,
        task_id=f"{run_id}:{batch_id}:{operation_id}:progress",
        run_id=run_id,
        agent_name="BatchProgressTracker",
        scope_type="operation",
        scope_id=operation_id,
        channel=batch_id,
        target_language="any",
        status=status,
        input_data={"batch_id": batch_id},
    )


def get_batch_progress(conn: sqlite3.Connection, run_id: str, batch_id: str) -> dict:
    """Return status counts for one batch."""
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM agent_tasks
        WHERE run_id = ? AND agent_name = 'BatchProgressTracker' AND channel = ?
        GROUP BY status
        """,
        (run_id, batch_id),
    ).fetchall()
    return {row["status"]: row["count"] for row in rows}


def print_progress_bar(conn: sqlite3.Connection, run_id: str) -> None:
    """Print a terminal progress bar for all tracked operations in a run."""
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM agent_tasks
        WHERE run_id = ? AND agent_name = 'BatchProgressTracker'
        GROUP BY status
        """,
        (run_id,),
    ).fetchall()
    counts = {row["status"]: row["count"] for row in rows}
    total = sum(counts.values())
    completed = counts.get("completed", 0) + counts.get("validated", 0)
    width = 10
    filled = int((completed / total) * width) if total else 0
    print(f"[{'=' * filled}>{' ' * max(width - filled - 1, 0)}] {completed}/{total} operations")
