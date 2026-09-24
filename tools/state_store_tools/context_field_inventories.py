from __future__ import annotations

import sqlite3
from typing import Any

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def upsert_context_field_inventory(
    conn: sqlite3.Connection,
    *,
    context_id: str,
    channel: str,
    run_id: str,
    full_chain: list[str] | None = None,
    inventory: dict[str, Any] | None = None,
    status: str = "pending",
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO context_field_inventories (
            context_id, channel, run_id, full_chain_json, inventory_json,
            status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(context_id, channel, run_id) DO UPDATE SET
            full_chain_json = excluded.full_chain_json,
            inventory_json = excluded.inventory_json,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (
            context_id,
            channel,
            run_id,
            dumps(full_chain or []),
            dumps(inventory),
            status,
            now,
            now,
        ),
    )
    conn.commit()


def get_context_field_inventory(
    conn: sqlite3.Connection, context_id: str, channel: str, run_id: str
) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM context_field_inventories
        WHERE context_id = ? AND channel = ? AND run_id = ?
        """,
        (context_id, channel, run_id),
    ).fetchone()
    return load_json_columns(row, ("full_chain_json", "inventory_json"))
