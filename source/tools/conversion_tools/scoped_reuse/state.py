"""Store additive scoped checkpoints and cache entries without changing legacy tables."""

import json


def initialize(conn):
    """Create only qualified C5 tables; callers own transactions."""
    conn.execute('''CREATE TABLE IF NOT EXISTS scoped_checkpoints (
        run_id TEXT NOT NULL, operation_identity TEXT NOT NULL, status TEXT NOT NULL,
        fingerprint TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(run_id,operation_identity))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS scoped_reuse_entries (
        run_id TEXT NOT NULL, category TEXT NOT NULL, identity TEXT NOT NULL, fingerprint TEXT NOT NULL,
        data_json TEXT NOT NULL, data_hash TEXT NOT NULL, files_json TEXT NOT NULL,
        PRIMARY KEY(run_id,category,identity,fingerprint))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS scoped_reuse_consumers (
        run_id TEXT NOT NULL, operation_identity TEXT NOT NULL, category TEXT NOT NULL, identity TEXT NOT NULL,
        fingerprint TEXT NOT NULL, status TEXT NOT NULL,
        PRIMARY KEY(run_id,operation_identity,category,identity,fingerprint))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS scoped_stale_evidence (
        run_id TEXT NOT NULL, operation_identity TEXT NOT NULL, reasons_json TEXT NOT NULL,
        PRIMARY KEY(run_id,operation_identity))''')


def checkpoints(conn, run_id):
    """Return persisted proof, including sticky invalidation state."""
    initialize(conn)
    from models.scoped_checkpoint import ScopedCheckpoint
    return {row[0]: ScopedCheckpoint.model_validate_json(row[1]) for row in conn.execute(
        'SELECT operation_identity,record_json FROM scoped_checkpoints WHERE run_id=?', (run_id,))}


def invalidate(conn, run_id, checkpoint, reasons):
    """Mark exact consumers stale while retaining artifacts, output files, and old proof."""
    checkpoint = checkpoint.model_copy(update={'status': 'stale'})
    conn.execute('UPDATE scoped_checkpoints SET status=?,record_json=? WHERE run_id=? AND operation_identity=?',
        ('stale', checkpoint.model_dump_json(), run_id, checkpoint.operation_identity))
    conn.execute('UPDATE scoped_reuse_consumers SET status=? WHERE run_id=? AND operation_identity=?',
                 ('stale', run_id, checkpoint.operation_identity))
    conn.execute('INSERT OR REPLACE INTO scoped_stale_evidence VALUES (?,?,?)',
                 (run_id, checkpoint.operation_identity, json.dumps(reasons)))
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE name='operation_service_contracts'").fetchone()
    if table:
        conn.execute('UPDATE operation_service_contracts SET status=? WHERE run_id=? AND operation_key=?',
                     ('planned', run_id, checkpoint.operation_key))


def save_checkpoint(conn, run_id, checkpoint):
    """Save proof only after complete preparation and final freshness verification."""
    conn.execute('INSERT OR REPLACE INTO scoped_checkpoints VALUES (?,?,?,?,?)',
        (run_id, checkpoint.operation_identity, checkpoint.status, checkpoint.fingerprint, checkpoint.model_dump_json()))
