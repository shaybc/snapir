from __future__ import annotations

import sqlite3

from models.conversion_models import ExcludedOpStep
from tools.state_store_tools._json import loads


def filter_opsteps_for_channel(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
) -> tuple[list[str], list[ExcludedOpStep]]:
    """Filter operation opSteps by opStep-level onlyFor rules."""
    operation = _source_artifact(conn, run_id, "operation", operation_id)
    if operation is None:
        raise KeyError(f"Operation source artifact not found: {operation_id}")
    metadata = loads(operation["metadata_json"], {}) or {}
    included: list[str] = []
    excluded: list[ExcludedOpStep] = []
    for opstep_id in metadata.get("steps", []):
        opstep = _source_artifact(conn, run_id, "opStep", opstep_id)
        opstep_metadata = loads(opstep["metadata_json"], {}) if opstep else {}
        only_for = opstep_metadata.get("only_for")
        if only_for is None:
            only_for = opstep_metadata.get("onlyFor")
        if _is_allowed_for_channel(only_for, channel):
            included.append(opstep_id)
        else:
            excluded.append(ExcludedOpStep(id=opstep_id, reason=f"onlyFor={only_for}"))
    return included, excluded


def _is_allowed_for_channel(only_for: object, channel: str) -> bool:
    if only_for is None or str(only_for).strip() == "":
        return True
    allowed_channels = {value.strip().lower() for value in str(only_for).split(",")}
    return channel.lower() in allowed_channels


def _source_artifact(
    conn: sqlite3.Connection,
    run_id: str,
    kind: str,
    logical_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM source_artifacts
        WHERE run_id = ? AND kind = ? AND logical_id = ?
        """,
        (run_id, kind, logical_id),
    ).fetchone()
