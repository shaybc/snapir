"""Invalidate recorded build results when their canonical POM changes."""

import hashlib
from pathlib import Path

from tools.state_store_tools._json import utc_now


def pom_hash(pom_path: str) -> str:
    """Return a content hash suitable for build and approval checkpoints."""
    return hashlib.sha256(Path(pom_path).read_bytes()).hexdigest()


def reconcile_pom_hash(conn, run_id: str, pom_path: str, operation_id: str | None, channel: str,
                       *, exclude_task_id: str = "") -> bool:
    """Mark affected build tasks/artifacts stale when a previously recorded POM changes."""
    path = str(Path(pom_path).resolve())
    digest = pom_hash(path)
    key = f"{run_id}:managed_pom:{path}"
    conn.execute("""CREATE TABLE IF NOT EXISTS managed_pom_checkpoints (
        checkpoint_id TEXT PRIMARY KEY, pom_hash TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    row = conn.execute("SELECT pom_hash FROM managed_pom_checkpoints WHERE checkpoint_id=?", (key,)).fetchone()
    changed = row is not None and row[0] != digest
    if changed:
        source_root = str(Path(path).parent / "src/main/java")
        conn.execute("""UPDATE agent_tasks SET status='needs_rerun', updated_at=? WHERE run_id=? AND
            status IN ('completed','validated') AND task_id IN (
            SELECT replace(artifact_id, ? || ':native_java:', '') FROM native_java_artifacts
            WHERE run_id=? AND substr(artifact_path,1,?)=? AND artifact_id<>?) AND task_id<>?""",
            (utc_now(), run_id, run_id, run_id, len(source_root), source_root,
             f"{run_id}:native_java:{exclude_task_id}", exclude_task_id))
        conn.execute("""UPDATE native_java_artifacts SET status='needs_rerun', updated_at=?
            WHERE run_id=? AND substr(artifact_path,1,?)=? AND artifact_id<>?""",
            (utc_now(), run_id, len(source_root), source_root, f"{run_id}:native_java:{exclude_task_id}"))
        parameters = [utc_now(), run_id]
        condition = ""
        if operation_id is not None:
            condition = " AND operation_id=? AND channel=?"
            parameters.extend([operation_id, channel])
        conn.execute("UPDATE generated_artifacts SET status='needs_rerun', updated_at=? WHERE run_id=?" + condition,
                     parameters)
        conn.execute("""UPDATE agent_tasks SET status='needs_rerun', updated_at=?
            WHERE run_id=? AND status IN ('completed','validated') AND
            (scope_type='operation' OR scope_type='build')""" +
            (" AND scope_id=? AND channel=?" if operation_id is not None else ""), parameters)
    conn.execute("""INSERT INTO managed_pom_checkpoints VALUES (?, ?, ?)
        ON CONFLICT(checkpoint_id) DO UPDATE SET pom_hash=excluded.pom_hash, updated_at=excluded.updated_at""",
                 (key, digest, utc_now()))
    conn.commit()
    return changed
