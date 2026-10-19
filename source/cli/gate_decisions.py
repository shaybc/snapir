"""Record CLI gate decisions using the persisted checkpoint and exact review report."""

from pathlib import Path
import sqlite3

from runtime.human_gates import record_decision
from runtime.workspace_paths import run_database_path, run_report_path


GATE_PHASES = {f"gate_{number}_{state}": number
               for number in range(1, 5) for state in ("pending", "rejected")}
GATE_PHASES.update({f"conversion_plan_{state}": "plan" for state in ("pending", "rejected")})


def pending_gate_number(directory: Path) -> int | str | None:
    """Read the eligible gate number from a run without changing its database."""
    database = run_database_path(directory)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
        run = conn.execute("SELECT current_phase FROM runs WHERE run_id=?", (directory.name,)).fetchone()
    return GATE_PHASES.get(run[0]) if run else None


def record_gate_decision(directory: Path, run_id: str, gate: int | str, decision: str) -> None:
    """Preserve CLI eligibility checks and bind the decision to the current report content."""
    if gate == 'plan':
        from models.common_models import RunConfig
        from models.pipeline_configuration import PipelineConfiguration
        from runtime.workspace_paths import run_profile_path
        from runtime.intake_plan import record_plan_decision
        from tools.state_store_tools.db import get_connection
        from tools.state_store_tools.runs import get_run
        if not run_database_path(directory).is_file():
            raise ValueError('Run database does not exist')
        conn = get_connection(str(run_database_path(directory)))
        try:
            run = get_run(conn, run_id)
            if run is None or run['current_phase'] not in {'conversion_plan_pending', 'conversion_plan_rejected'}:
                raise ValueError('Run is not waiting for plan approval')
            profile = PipelineConfiguration.model_validate_json(run_profile_path(directory).read_text(encoding='utf-8'))
            config = RunConfig.model_validate(run['run_config_json'])
            record_plan_decision(conn, config, profile, directory, decision)
        finally:
            conn.close()
        return
    from tools.state_store_tools.operation_progress import active_operation, operation_directory
    from tools.state_store_tools.db import get_connection
    from runtime.human_gates import operation_gate_scope
    connection = sqlite3.connect(run_database_path(directory).as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        current = active_operation(connection, run_id)
    finally:
        connection.close()
    report_directory = operation_directory(directory, current['operation_key']) if current else directory
    if gate == 1 and run_report_path(report_directory, "gate_1_report.md").is_file():
        from runtime.gate_one_reports import read_gate_one_reports
        report = read_gate_one_reports(report_directory)
    else:
        report = run_report_path(report_directory, f"gate_{gate}_report.txt").read_text(encoding="utf-8")
    database = run_database_path(directory)
    with sqlite3.connect(database.as_uri() + "?mode=rw", uri=True) as conn:
        run = conn.execute("SELECT current_phase FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None or run[0] not in {f"gate_{gate}_pending", f"gate_{gate}_rejected"}:
            raise ValueError("Run is not waiting at this gate")
        with operation_gate_scope(current['operation_key'] if current else ''):
            record_decision(conn, run_id, gate, report, decision)
