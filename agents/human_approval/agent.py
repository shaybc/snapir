from __future__ import annotations

import sqlite3
from typing import Callable

from tools.state_store_tools.runs import update_run_status


class HumanApprovalAgent:
    """Present human gate reports and return approval decisions."""

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        self.conn = conn
        self.input_fn = input_fn
        self.output_fn = output_fn

    def present_gate(
        self,
        gate_number: int,
        report: str,
        run_id: str,
    ) -> bool:
        """Print a gate report, read yes/no input, and log the decision to runs."""
        self.output_fn(report)
        answer = self.input_fn(f"Approve Human Gate {gate_number}? (yes/no): ").strip().lower()
        approved = answer in {"yes", "y"}
        if self.conn:
            status = "approved" if approved else "rejected"
            update_run_status(self.conn, run_id, status, current_phase=f"gate_{gate_number}_{status}")
        return approved
