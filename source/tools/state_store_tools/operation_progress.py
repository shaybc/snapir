"""Store sequential operation checkpoints inside the existing run database."""

import json
from pathlib import Path
from tools.component_inventory_tools.identity import stable_id


def initialize_progress(conn, run_id, order, *, plan_hash=None):
    """Add pending operations once; reject silent replacement of an executing plan."""
    conn.execute('''CREATE TABLE IF NOT EXISTS operation_workflow_progress (
        run_id TEXT NOT NULL, operation_key TEXT NOT NULL, position INTEGER NOT NULL,
        status TEXT NOT NULL, phase TEXT NOT NULL, publication_json TEXT,
        PRIMARY KEY(run_id,operation_key))''')
    existing = conn.execute('SELECT operation_key FROM operation_workflow_progress WHERE run_id=? ORDER BY position', (run_id,)).fetchall()
    if existing and [row[0] for row in existing] != list(order):
        raise ValueError('Executing operation order cannot be replaced silently')
    if plan_hash is not None:
        conn.execute('CREATE TABLE IF NOT EXISTS operation_workflow_plans (run_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL)')
        prior = conn.execute('SELECT plan_hash FROM operation_workflow_plans WHERE run_id=?', (run_id,)).fetchone()
        if prior and prior[0] != plan_hash:
            raise ValueError('Executing plan evidence changed; start a revised run instead of resetting completed work')
    with conn:
        if plan_hash is not None:
            conn.execute('INSERT OR IGNORE INTO operation_workflow_plans VALUES (?,?)', (run_id, plan_hash))
        for index, key in enumerate(order):
            conn.execute('INSERT OR IGNORE INTO operation_workflow_progress VALUES (?,?,?,?,?,NULL)',
                         (run_id, key, index, 'pending', 'operation_pending'))


def progress_rows(conn, run_id):
    """Return saved operation progress without creating tables on older runs."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='operation_workflow_progress'").fetchone():
        return []
    rows = conn.execute('SELECT * FROM operation_workflow_progress WHERE run_id=? ORDER BY position', (run_id,))
    return [dict(row) for row in rows]


def save_progress(conn, run_id, key, status, phase, publication=None):
    """Commit a workflow phase, retaining any prepared publication for recovery."""
    with conn:
        conn.execute('''UPDATE operation_workflow_progress SET status=?,phase=?,
            publication_json=COALESCE(?,publication_json) WHERE run_id=? AND operation_key=?''',
            (status, phase, json.dumps(publication, sort_keys=True) if publication is not None else None, run_id, key))


def operation_directory(directory, key):
    """Resolve a stable operation report/output folder safely within its run."""
    root = (Path(directory) / 'operation_workflows').resolve()
    path = (root / stable_id(key)[:20]).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Unsafe operation workflow directory')
    return path


def active_operation(conn, run_id):
    """Return the first incomplete operation, or None when every operation is complete."""
    return next((row for row in progress_rows(conn, run_id) if row['status'] != 'completed'), None)
