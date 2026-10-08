"""Verify that approvals cannot bypass checks or survive changed reports."""

import sqlite3

from runtime.human_gates import evaluate_gate, record_decision


def test_approval_is_bound_to_reviewed_report():
    with sqlite3.connect(":memory:") as conn:
        assert evaluate_gate(conn, "run", 1, "report", "human", True) == "pending"
        record_decision(conn, "run", 1, "report", "approved")
        assert evaluate_gate(conn, "run", 1, "report", "human", True) == "approved"
        assert evaluate_gate(conn, "run", 1, "changed", "human", True) == "pending"


def test_automatic_policy_does_not_bypass_failed_checks():
    with sqlite3.connect(":memory:") as conn:
        assert evaluate_gate(conn, "run", 1, "report", "automatic", False) == "blocked"
        assert evaluate_gate(conn, "run", 1, "report", "automatic", True) == "approved"
        assert conn.execute("SELECT policy FROM runtime_gate_decisions").fetchone()[0] == "automatic"


def test_rejection_is_not_overridden_by_automatic_policy():
    with sqlite3.connect(":memory:") as conn:
        record_decision(conn, "run", 1, "report", "rejected")
        assert evaluate_gate(conn, "run", 1, "report", "automatic", True) == "rejected"
