from __future__ import annotations

import sqlite3
from typing import Any

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def make_task_key(
    run_id: str,
    agent_name: str,
    scope_type: str,
    scope_id: str,
    channel: str,
    target_language: str,
    schema_version: str = "v1",
) -> str:
    return (
        f"{run_id}:{agent_name}:{scope_type}:{scope_id}:"
        f"{channel}:{target_language}:{schema_version}"
    )


def upsert_agent_task(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    agent_name: str,
    scope_type: str,
    scope_id: str,
    channel: str,
    target_language: str = "any",
    schema_version_key: str = "v1",
    status: str = "pending",
    blocking_reason: str | None = None,
    attempt_number: int = 0,
    max_retries: int = 3,
    input_data: Any = None,
    output_data: Any = None,
    error_message: str | None = None,
    task_id: str | None = None,
) -> str:
    now = utc_now()
    task_id = task_id or make_task_key(
        run_id, agent_name, scope_type, scope_id, channel, target_language, schema_version_key
    )
    conn.execute(
        """
        INSERT INTO agent_tasks (
            task_id, run_id, agent_name, scope_type, scope_id, channel,
            target_language, schema_version_key, status, blocking_reason,
            attempt_number, max_retries, input_json, output_json, error_message,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(task_id) DO UPDATE SET
            status = excluded.status,
            blocking_reason = excluded.blocking_reason,
            attempt_number = excluded.attempt_number,
            max_retries = excluded.max_retries,
            input_json = excluded.input_json,
            output_json = excluded.output_json,
            error_message = excluded.error_message,
            updated_at = excluded.updated_at
        """,
        (
            task_id,
            run_id,
            agent_name,
            scope_type,
            scope_id,
            channel,
            target_language,
            schema_version_key,
            status,
            blocking_reason,
            attempt_number,
            max_retries,
            dumps(input_data),
            dumps(output_data),
            error_message,
            now,
            now,
        ),
    )
    conn.commit()
    return task_id


def get_agent_task(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
    return load_json_columns(row, ("input_json", "output_json"))


def update_task_status(
    conn: sqlite3.Connection,
    task_id: str,
    status: str,
    *,
    blocking_reason: str | None = None,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE agent_tasks
        SET status = ?, blocking_reason = ?, error_message = ?, updated_at = ?
        WHERE task_id = ?
        """,
        (status, blocking_reason, error_message, utc_now(), task_id),
    )
    conn.commit()
