"""Display saved migration progress and actionable checkpoint guidance."""

import json
import sqlite3
import sys

from runtime.workflow_stages import STAGES, workflow_stage
from runtime.workspace_paths import run_database_path, run_profile_path, run_report_path
from cli.workflow_subsections import active_subsections, subsection_lines
from cli.workflow_situation import situation_lines


def _print_progress(text):
    """Keep progress readable on Windows consoles with legacy encodings."""
    try:
        (text + "✓→─—").encode(getattr(sys.stdout, "encoding", None) or "utf-8")
    except UnicodeEncodeError:
        text = text.translate(str.maketrans({"✓": "[V]", "→": "->", "─": "-", "—": "-"}))
    print(text)


def _gate_decision(directory, gate):
    """Read only the decision matching the gate's current report content."""
    try:
        from tools.state_store_tools.operation_progress import active_operation, operation_directory
        from runtime.human_gates import gate_report_hash, operation_gate_scope
        with sqlite3.connect(run_database_path(directory).as_uri() + "?mode=ro", uri=True) as state:
            state.row_factory = sqlite3.Row
            current = active_operation(state, directory.name)
        report_directory = operation_directory(directory, current['operation_key']) if current and gate != 'plan' else directory
        if gate == 'plan':
            report = run_report_path(directory, 'conversion_plan.md').read_text(encoding='utf-8')
        elif gate == "1":
            from runtime.gate_one_reports import read_gate_one_reports
            report = read_gate_one_reports(report_directory)
        else:
            report = run_report_path(report_directory, f"gate_{gate}_report.txt").read_text(encoding="utf-8")
        import hashlib
        with operation_gate_scope(current['operation_key'] if current and gate != 'plan' else ''):
            digest = gate_report_hash(report)
        with sqlite3.connect(run_database_path(directory).as_uri() + "?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT decision FROM runtime_gate_decisions WHERE run_id=? AND gate_number=? AND report_hash=?",
                               (directory.name, 0 if gate == 'plan' else int(gate), digest)).fetchone()
            return row[0] if row else None
    except (OSError, ValueError, sqlite3.Error):
        return None


def checkpoint_guidance(directory, status, phase):
    """Explain why the saved checkpoint is waiting and what the user can do next."""
    if phase.startswith('conversion_plan_'):
        report = str(run_report_path(directory, 'conversion_plan.md'))
        if phase == 'conversion_plan_approved' or (phase == 'conversion_plan_pending' and _gate_decision(directory, 'plan') == 'approved'):
            return ['Conversion plan approved', 'Plan: ' + report], 'Resume to convert operations sequentially in the approved order.'
        if phase == 'conversion_plan_blocked':
            return ['Conversion plan evidence changed or dependencies are blocked', 'Plan: ' + report], 'Resolve the reported issue and refresh intake before approval.'
        return ['Conversion plan awaiting approval' if phase.endswith('pending') else 'Conversion plan rejected',
                'Plan: ' + report], 'Review the plan, then choose Approve a gate or Reject a gate (plan).'
    if phase == "conversion_pending":
        profile_path = run_profile_path(directory)
        if profile_path.is_file() and json.loads(profile_path.read_text(encoding="utf-8")).get("conversion_strategy") == "behavior_units":
            if status == "failed":
                return ["Native behavior-unit conversion failed; inspect the unit name and correction feedback in the logs"], "Resolve the reported evidence, contract or build issue, then resume."
            return ["Complete-format and configured-step conversion is pending"], "Resume to continue native behavior-unit conversion."
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
        decision = _gate_decision(directory, gate)
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
    from tools.state_store_tools.operation_progress import progress_rows, operation_directory
    progress = []
    try:
        with sqlite3.connect(run_database_path(directory).as_uri() + '?mode=ro', uri=True) as state:
            state.row_factory = sqlite3.Row
            progress = progress_rows(state, directory.name)
        if progress:
            completed = sum(item['status'] == 'completed' for item in progress)
            _print_progress(f'Operations completed: {completed}/{len(progress)}')
            current = next((item for item in progress if item['status'] != 'completed'), None)
            if current:
                _print_progress('Current operation: ' + current['operation_key'] + ' — ' + current['phase'])
                _print_progress('Operation reports: ' + str(operation_directory(directory, current['operation_key']) / 'reports'))
    except (OSError, sqlite3.Error):
        pass
    try:
        with sqlite3.connect(run_database_path(directory).as_uri() + "?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT status, current_phase FROM runs WHERE run_id=?", (directory.name,)).fetchone()
            approved_three = bool(row and row[1] == "gate_3_pending" and row[0] == "paused"
                                  and _gate_decision(directory, "3") == "approved")
            if approved_three:
                row = (row[0], "service_generation_pending")
            # Legacy subsection queries aggregate the whole run; do not attribute earlier operations' evidence to the current one.
            subsections = active_subsections(conn, directory, row[0], row[1] or "") if row and not progress else []
            if approved_three:
                subsections = [(key, title.removesuffix(" (checkpoint detail unavailable)") + " (waiting for Resume)"
                                if state == "current" else title, state, children)
                               for key, title, state, children in subsections]
        if row is None:
            return
        status, phase = row
        current = list(STAGES).index(workflow_stage(phase))
        details, next_step = checkpoint_guidance(directory, status, phase or "")
        if approved_three:
            details, next_step = ["Gate 3 approved; service generation is waiting for Resume"], "Resume this run to start service generation and validation."
    except (OSError, ValueError, sqlite3.Error):
        return
    completed = phase in {"migration_approved", "dry_run_complete"}
    _print_progress("\n\nCurrent operation workflow progress" if progress and not completed else "\n\nMigration progress")
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
            if approved_three:
                description = "waiting for resume"
        _print_progress(f"{marker} {index + 1}. {label} ({description.upper()})")
        if index == current:
            if not completed:
                for line in subsection_lines(subsections):
                    _print_progress(line)
            for detail in details:
                print(f"        {detail}")
    print(f"\nNext step: {next_step}")
    _print_progress("\n[V] Completed   → Current stage   [ ] Pending   ! Requires attention\n")
    for line in situation_lines(directory, status, phase, details, next_step):
        _print_progress(line)
    print()
