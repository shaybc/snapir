from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from tools.artifact_registry_tools.component_registry import (
    get_component_by_id,
    get_used_by_validated_count,
)
from tools.common_lib_tools.build import run_common_lib_build


def maybe_promote(
    conn: sqlite3.Connection,
    component_id: str,
    common_lib_root: str,
    run_id: str,
) -> bool:
    """Promote a validated component once it is reused by at least two validated operations."""
    if get_used_by_validated_count(conn, component_id) < 2:
        return False
    return promote_to_common_lib(conn, component_id, common_lib_root, run_id)


def promote_to_common_lib(
    conn: sqlite3.Connection,
    component_id: str,
    common_lib_root: str,
    run_id: str,
) -> bool:
    """Copy a generated component into common-lib and run the common-lib build."""
    record = get_component_by_id(conn, component_id)
    if record is None or not record.generated_path:
        return False
    source_path = Path(record.generated_path)
    if not source_path.exists():
        return False
    common_root = Path(common_lib_root)
    destination = common_root / "src" / "main" / "java" / source_path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    result = run_common_lib_build(common_lib_root)
    return result.success
