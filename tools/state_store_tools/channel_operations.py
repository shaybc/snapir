from __future__ import annotations

import sqlite3

from tools.state_store_tools._json import row_to_dict, utc_now


def upsert_channel_operation(
    conn: sqlite3.Connection,
    *,
    operation_name: str,
    channel: str,
    xml_file_path: str,
    run_id: str,
) -> None:
    conn.execute(
        """
        INSERT INTO channel_operations (operation_name, channel, xml_file_path, run_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(operation_name, channel, run_id) DO UPDATE SET
            xml_file_path = excluded.xml_file_path
        """,
        (operation_name, channel, xml_file_path, run_id),
    )
    conn.commit()


def get_channel_operation(
    conn: sqlite3.Connection, operation_name: str, channel: str, run_id: str
) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM channel_operations
        WHERE operation_name = ? AND channel = ? AND run_id = ?
        """,
        (operation_name, channel, run_id),
    ).fetchone()
    return row_to_dict(row)


def upsert_operation(
    conn: sqlite3.Connection,
    *,
    operation_id: str,
    channel: str,
    run_id: str,
    xml_file_path: str | None = None,
    status: str = "pending",
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO operations (
            operation_id, channel, run_id, xml_file_path, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(operation_id, channel, run_id) DO UPDATE SET
            xml_file_path = excluded.xml_file_path,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (operation_id, channel, run_id, xml_file_path, status, now, now),
    )
    conn.commit()


def get_operation(
    conn: sqlite3.Connection, operation_id: str, channel: str, run_id: str
) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM operations
        WHERE operation_id = ? AND channel = ? AND run_id = ?
        """,
        (operation_id, channel, run_id),
    ).fetchone()
    return row_to_dict(row)
