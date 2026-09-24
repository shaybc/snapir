from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def upsert_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    run_mode: str,
    status: str = "started",
    current_phase: str | None = None,
    run_config: dict[str, Any] | BaseModel | None = None,
    schema_version: str = "v1",
) -> None:
    now = utc_now()
    if isinstance(run_config, BaseModel):
        run_config = run_config.model_dump(mode="json")
    conn.execute(
        """
        INSERT INTO runs (
            run_id, run_mode, status, current_phase, run_config_json,
            created_at, updated_at, schema_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            run_mode = excluded.run_mode,
            status = excluded.status,
            current_phase = excluded.current_phase,
            run_config_json = excluded.run_config_json,
            updated_at = excluded.updated_at,
            schema_version = excluded.schema_version
        """,
        (
            run_id,
            run_mode,
            status,
            current_phase,
            dumps(run_config),
            now,
            now,
            schema_version,
        ),
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return load_json_columns(row, ("run_config_json",))


def update_run_status(
    conn: sqlite3.Connection, run_id: str, status: str, current_phase: str | None = None
) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status = ?, current_phase = ?, updated_at = ?
        WHERE run_id = ?
        """,
        (status, current_phase, utc_now(), run_id),
    )
    conn.commit()
