from __future__ import annotations

import sqlite3

from tools.state_store_tools._json import row_to_dict


def upsert_tag(
    conn: sqlite3.Connection,
    *,
    tag_name: str,
    fqcn: str,
    run_id: str,
    channel: str | None = None,
    source_dse_ini: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO tag_registry (tag_name, fqcn, channel, source_dse_ini, run_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(tag_name, channel, run_id) DO UPDATE SET
            fqcn = excluded.fqcn,
            source_dse_ini = excluded.source_dse_ini
        """,
        (tag_name, fqcn, channel, source_dse_ini, run_id),
    )
    conn.commit()


def get_tag(
    conn: sqlite3.Connection, tag_name: str, run_id: str, channel: str | None = None
) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM tag_registry
        WHERE tag_name = ? AND run_id = ? AND channel IS ?
        """,
        (tag_name, run_id, channel),
    ).fetchone()
    return row_to_dict(row)
