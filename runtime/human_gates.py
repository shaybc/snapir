"""Persist gate decisions bound to the exact report under review."""

import hashlib
import sqlite3

from tools.state_store_tools._json import utc_now


def initialize_gates(conn: sqlite3.Connection) -> None:
    """Create runtime approval storage without changing existing state tables."""
    conn.execute("""CREATE TABLE IF NOT EXISTS runtime_gate_decisions (
        run_id TEXT NOT NULL, gate_number INTEGER NOT NULL, report_hash TEXT NOT NULL,
        decision TEXT NOT NULL, policy TEXT NOT NULL, decided_at TEXT NOT NULL,
        PRIMARY KEY (run_id, gate_number, report_hash)
    )""")
    conn.commit()


def record_decision(conn, run_id: str, gate_number: int, report: str,
                    decision: str, policy: str = "human") -> None:
    """Store an explicit approval or rejection against report content."""
    if decision not in {"approved", "rejected"}:
        raise ValueError("Gate decision must be approved or rejected")
    initialize_gates(conn)
    conn.execute("""INSERT INTO runtime_gate_decisions VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, gate_number, report_hash) DO UPDATE SET
        decision=excluded.decision, policy=excluded.policy, decided_at=excluded.decided_at""",
        (run_id, gate_number, hashlib.sha256(report.encode()).hexdigest(), decision, policy, utc_now()))
    conn.commit()


def evaluate_gate(conn, run_id: str, gate_number: int, report: str,
                  policy: str, checks_passed: bool) -> str:
    """Return approved, rejected, or pending; failed checks always block execution."""
    if not checks_passed:
        return "blocked"
    initialize_gates(conn)
    digest = hashlib.sha256(report.encode()).hexdigest()
    row = conn.execute("""SELECT decision FROM runtime_gate_decisions
        WHERE run_id=? AND gate_number=? AND report_hash=?""", (run_id, gate_number, digest)).fetchone()
    if row:
        return row[0]
    if policy in {"automatic", "skip"}:
        record_decision(conn, run_id, gate_number, report, "approved", policy)
        return "approved"
    if policy != "human":
        raise ValueError("Unknown gate policy")
    return "pending"
