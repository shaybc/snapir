from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.state_store_tools.channel_operations import get_channel_operation


class OperationXmlNotFoundError(FileNotFoundError):
    """Raised when an operation XML mapping or file cannot be found."""


def load_operation_xml(
    conn: sqlite3.Connection,
    operation_name: str,
    channel: str,
    run_id: str,
    composer_root: str,
) -> str:
    """Read the raw operation XML mapped to an operation/channel pair."""
    xml_file_path = get_operation_xml_path(conn, operation_name, channel, run_id)
    path = Path(composer_root) / xml_file_path
    if not path.exists():
        raise OperationXmlNotFoundError(f"Operation XML file not found: {path}")
    return path.read_text(encoding="utf-8")


def get_operation_xml_path(
    conn: sqlite3.Connection,
    operation_name: str,
    channel: str,
    run_id: str,
) -> str:
    """Return the mapped operation XML path without reading the file."""
    row = get_channel_operation(conn, operation_name, channel, run_id)
    if row is None:
        raise OperationXmlNotFoundError(
            f"Operation XML mapping not found: {operation_name}/{channel}/{run_id}"
        )
    return str(row["xml_file_path"])
