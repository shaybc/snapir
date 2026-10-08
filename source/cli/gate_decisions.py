"""Record CLI gate decisions using the persisted checkpoint and exact review report."""

from pathlib import Path
import sqlite3

from runtime.human_gates import record_decision
from runtime.workspace_paths import run_database_path, run_report_path


GATE_PHASES = {f"gate_{number}_{state}": number
               for number in range(1, 5) for state in ("pending", "rejected")}


def pending_gate_number(directory: Path) -> int | None:
    """Read the eligible gate number from a run without changing its database."""
    database = run_database_path(directory)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
        run = conn.execute("SELECT current_phase FROM runs WHERE run_id=?", (directory.name,)).fetchone()
    return GATE_PHASES.get(run[0]) if run else None


def record_gate_decision(directory: Path, run_id: str, gate: int, decision: str) -> None:
    """Preserve CLI eligibility checks and bind the decision to the current report content."""
    if gate == 1 and run_report_path(directory, "gate_1_report.md").is_file():
        from runtime.gate_one_reports import read_gate_one_reports
        report = read_gate_one_reports(directory)
    else:
        report = run_report_path(directory, f"gate_{gate}_report.txt").read_text(encoding="utf-8")
    database = run_database_path(directory)
    with sqlite3.connect(database.as_uri() + "?mode=rw", uri=True) as conn:
        run = conn.execute("SELECT current_phase FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None or run[0] not in {f"gate_{gate}_pending", f"gate_{gate}_rejected"}:
            raise ValueError("Run is not waiting at this gate")
        record_decision(conn, run_id, gate, report, decision)
