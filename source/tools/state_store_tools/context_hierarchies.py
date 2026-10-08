from __future__ import annotations

import sqlite3

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def upsert_context_hierarchy(
    conn: sqlite3.Connection,
    *,
    context_id: str,
    run_id: str,
    chain: list[str],
    root_id: str,
    has_cycle: bool = False,
) -> None:
    conn.execute(
        """
        INSERT INTO context_hierarchies (
            context_id, run_id, chain_json, root_id, has_cycle, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(context_id, run_id) DO UPDATE SET
            chain_json = excluded.chain_json,
            root_id = excluded.root_id,
            has_cycle = excluded.has_cycle
        """,
        (context_id, run_id, dumps(chain), root_id, int(has_cycle), utc_now()),
    )
    conn.commit()


def get_context_hierarchy(conn: sqlite3.Connection, context_id: str, run_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM context_hierarchies
        WHERE context_id = ? AND run_id = ?
        """,
        (context_id, run_id),
    ).fetchone()
    return load_json_columns(row, ("chain_json",))
