from __future__ import annotations

import shutil
import sqlite3
import subprocess
from runtime.java_toolchain import run_java, java_version
from pathlib import Path

from tools.artifact_registry_tools.component_registry import (
    get_component_by_id,
    get_used_by_validated_count,
)


def promote_to_common_lib(
    conn: sqlite3.Connection,
    component_id: str,
    common_lib_root: str,
    run_id: str,
) -> bool:
    if get_used_by_validated_count(conn, component_id) < 2:
        return False

    record = get_component_by_id(conn, component_id)
    if record is None:
        return False
    if record.generated_path == "":
        return False

    source_path = Path(record.generated_path)
    if not source_path.exists():
        return False

    common_root = Path(common_lib_root)
    destination = common_root / "src" / source_path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)

    run_java(["mvn", "install"], cwd=common_root, check=True)
    return True


def convert_framework_tags(
    conn: sqlite3.Connection,
    tag_registry_channel: str,
    common_lib_root: str,
    run_id: str,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT fqcn FROM tag_registry
        WHERE run_id = ? AND channel = ?
        ORDER BY tag_name
        """,
        (run_id, tag_registry_channel),
    ).fetchall()
    return [row["fqcn"] for row in rows]
