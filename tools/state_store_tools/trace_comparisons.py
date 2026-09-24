from __future__ import annotations

import sqlite3
from typing import Any

from tools.state_store_tools._json import dumps, load_json_columns, utc_now


def insert_trace_comparison(
    conn: sqlite3.Connection,
    *,
    comparison_id: str,
    operation_id: str,
    channel: str,
    run_id: str,
    scenario: str,
    matched: bool = False,
    step_sequence_match: bool | None = None,
    rc_per_step_match: bool | None = None,
    context_writes_match: bool | None = None,
    reply_format_match: bool | None = None,
    final_xml_match: bool | None = None,
    failure_class: str | None = None,
    comparison: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO trace_comparisons (
            comparison_id, operation_id, channel, run_id, scenario, matched,
            step_sequence_match, rc_per_step_match, context_writes_match,
            reply_format_match, final_xml_match, failure_class, comparison_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            comparison_id,
            operation_id,
            channel,
            run_id,
            scenario,
            int(matched),
            None if step_sequence_match is None else int(step_sequence_match),
            None if rc_per_step_match is None else int(rc_per_step_match),
            None if context_writes_match is None else int(context_writes_match),
            None if reply_format_match is None else int(reply_format_match),
            None if final_xml_match is None else int(final_xml_match),
            failure_class,
            dumps(comparison),
            utc_now(),
        ),
    )
    conn.commit()


def get_trace_comparison(conn: sqlite3.Connection, comparison_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM trace_comparisons WHERE comparison_id = ?", (comparison_id,)
    ).fetchone()
    return load_json_columns(row, ("comparison_json",))
