"""Persist option-two snapshots and attempts without altering legacy task schemas."""

import json
from tools.state_store_tools._json import utc_now

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS behavior_snapshots (
        run_id TEXT NOT NULL, category TEXT NOT NULL, identity TEXT NOT NULL,
        fingerprint TEXT NOT NULL, status TEXT NOT NULL, data_json TEXT NOT NULL,
        error TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(run_id,category,identity))""",
    """CREATE TABLE IF NOT EXISTS behavior_attempts (
        run_id TEXT NOT NULL, category TEXT NOT NULL, identity TEXT NOT NULL,
        fingerprint TEXT NOT NULL, attempt INTEGER NOT NULL, request_json TEXT NOT NULL,
        response TEXT, error TEXT, created_at TEXT NOT NULL,
        PRIMARY KEY(run_id,category,identity,fingerprint,attempt))""",
]


def initialize(conn):
    """Add strategy-specific state to a new or existing database."""
    for statement in SCHEMA:
        conn.execute(statement)
    conn.commit()


def snapshot(conn, run_id, category, identity):
    """Return a saved snapshot or None, including its acceptance identity."""
    row = conn.execute("SELECT * FROM behavior_snapshots WHERE run_id=? AND category=? AND identity=?",
                       (run_id, category, identity)).fetchone()
    return dict(row) if row else None


def save(conn, run_id, category, identity, fingerprint, data, status="accepted", error=None):
    """Replace current evidence and clear stale errors when accepted."""
    conn.execute("""INSERT INTO behavior_snapshots VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(run_id,category,identity) DO UPDATE SET fingerprint=excluded.fingerprint,
        status=excluded.status,data_json=excluded.data_json,error=excluded.error,updated_at=excluded.updated_at""",
        (run_id, category, identity, fingerprint, status, json.dumps(data), error, utc_now()))
    conn.commit()
