"""Display saved migration progress and actionable checkpoint guidance."""

import json
import sqlite3
import sys

from runtime.workflow_stages import STAGES, workflow_stage
from runtime.workspace_paths import run_database_path, run_profile_path, run_report_path


def _print_progress(text):
    """Keep progress readable on Windows consoles with legacy encodings."""
    try:
        (text + "✓→─—").encode(getattr(sys.stdout, "encoding", None) or "utf-8")
    except UnicodeEncodeError:
        text = text.translate(str.maketrans({"✓": "[V]", "→": "->", "─": "-", "—": "-"}))
    print(text)


def checkpoint_guidance(directory, status, phase):
    """Explain why the saved checkpoint is waiting and what the user can do next."""
    if phase == "conversion_pending":
        if status == "failed":
            return ["Component conversion failed; inspect the model response and error in the run logs"], (
                "Review the conversion error above and the verbose model log, then resume after resolving the cause.")
        if not run_report_path(directory, "managed_conversion_results.json").is_file():
            return ["Dependency check completed; ready for component conversion"], "Resume this run to start component conversion."
        return ["Conversion is pending; inspect the component conversion results for outstanding failures"], (
            "Review the component conversion reports, resolve any failures, then resume this run.")
    if phase == "closures_blocked":
        return ["Dependency check found unresolved dependencies"], "Open the dependency closure report and resolve its blocking issues."
    if phase.startswith("gate_"):
        gate = phase.split("_")[1]
        decision = None
        try:
            if gate == "1":
                from runtime.gate_one_reports import read_gate_one_reports
                report = read_gate_one_reports(directory)
            else:
                report = run_report_path(directory, f"gate_{gate}_report.txt").read_text(encoding="utf-8")
            import hashlib
            with sqlite3.connect(run_database_path(directory).as_uri() + "?mode=ro", uri=True) as conn:
                row = conn.execute("SELECT decision FROM runtime_gate_decisions WHERE run_id=? AND gate_number=? AND report_hash=?",
                                   (directory.name, int(gate), hashlib.sha256(report.encode()).hexdigest())).fetchone()
                decision = row[0] if row else None
        except (OSError, ValueError, sqlite3.Error):
            pass
        if decision == "approved":
            return [f"Gate {gate} approved"], "Resume this run to continue."
        if decision == "rejected" or phase.endswith("rejected"):
            return [f"Gate {gate} rejected"], "Review the gate report and resolve the review concerns before continuing."
        return [f"Gate {gate} awaiting review"], f"Review the Gate {gate} report, then choose Approve a gate or Reject a gate."
    if phase == "planning_inputs_ready":
        return ["Intake completed; you may review the intake reports before planning",
                "Reports: " + str(directory / "reports" / "1_intake_and_legacy_analysis")], (
                    "Optionally review the intake reports, then choose Resume a migration to begin migration planning.")
    if phase in {"migration_approved", "dry_run_complete"}:
        return ["Final validation completed"], "Review the final validation and delivery reports."
    if status in {"blocked", "failed", "stopped"}:
        return [f"Run {status} at checkpoint: {phase}"], "Review the stage reports and logs, resolve the reported issue, then resume when supported."
    return [f"Saved checkpoint: {phase or 'No checkpoint'}"], "Resume this run to continue; inspect the stage reports for review requirements."


def display_workflow_progress(directory):
    """Print seven-stage progress from read-only state without affecting execution."""
    try:
        with sqlite3.connect(run_database_path(directory).as_uri() + "?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT status, current_phase FROM runs WHERE run_id=?", (directory.name,)).fetchone()
        if row is None:
            return
        status, phase = row
        current = list(STAGES).index(workflow_stage(phase))
        details, next_step = checkpoint_guidance(directory, status, phase or "")
    except (OSError, ValueError, sqlite3.Error):
        return
    completed = phase in {"migration_approved", "dry_run_complete"}
    _print_progress("\n\nMigration progress")
    _print_progress("─" * 68)
    for index, label in enumerate(STAGES.values()):
        if index < current or completed:
            marker, description = "[V]", "completed"
        elif index > current:
            marker, description = "[ ]", "pending"
        else:
            marker = "!" if status in {"blocked", "failed", "stopped"} else "→"
            description = status if status in {"blocked", "failed", "stopped", "in_progress"} else "waiting"
            if phase == "planning_inputs_ready" and status == "paused":
                description = "ready to start"
        _print_progress(f"{marker} {index + 1}. {label} ({description.upper()})")
        if index == current:
            for detail in details:
                print(f"        {detail}")
    print(f"\nNext step: {next_step}")
    _print_progress("\n[V] Completed   → Current stage   [ ] Pending   ! Requires attention\n")
