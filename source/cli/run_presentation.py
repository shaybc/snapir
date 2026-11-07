"""Read and present small run metadata for every migration selection menu."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3

from runtime.workflow_stages import workflow_stage_label
from runtime.workspace_paths import run_database_path


def _time(value):
    return datetime.fromisoformat(value).astimezone().strftime('%d %b %Y %H:%M:%S %Z') if value else 'Not yet'


def read_run_summary(directory):
    """Read identity and targeted state rows without opening source, map or report files."""
    from cli.configuration_review import safe_value
    directory = Path(directory)
    identity = json.loads((directory / 'state/run_identity.json').read_text(encoding='utf-8'))
    if identity['run_id'] != directory.name:
        raise ValueError('Run identity does not match its folder')
    with sqlite3.connect(run_database_path(directory).as_uri() + '?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute('SELECT run_id,status,current_phase,created_at,updated_at FROM runs WHERE run_id=?',
                           (directory.name,)).fetchone()
        if run is None:
            raise ValueError('Run not found')
        decision = None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_gate_decisions'").fetchone():
            decision = conn.execute('SELECT gate_number,decision,decided_at FROM runtime_gate_decisions '
                                    'WHERE run_id=? ORDER BY decided_at DESC LIMIT 1', (directory.name,)).fetchone()
    activity_path = directory / 'state/run_activity.json'
    activity = json.loads(activity_path.read_text(encoding='utf-8')) if activity_path.is_file() else {}
    resumed = activity.get('last_resumed_at')
    timestamps = [identity['created_at'], run['updated_at']]
    if resumed:
        timestamps.append(resumed)
    if decision:
        timestamps.append(decision['decided_at'])
    latest = max(timestamps, key=datetime.fromisoformat)
    phase = run['current_phase'] or 'No checkpoint'
    stage = 'Conversion plan review' if phase.startswith('conversion_plan_') else workflow_stage_label(phase)
    label = (f"{directory.name} | {identity['configuration_name']} | {_time(latest)} | "
             f"{run['status']} | {stage} | {phase} | {identity['channels']} | {identity['operations']}")
    decision_text = 'None recorded'
    if decision:
        gate = 'Conversion plan' if decision['gate_number'] == 0 else f"Gate {decision['gate_number']}"
        decision_text = f"{gate} {decision['decision']} at {_time(decision['decided_at'])}"
    details = [
        f'Run: {directory.name}',
        f"Configuration: {identity['configuration_name']}",
        f"Configuration file: {identity['configuration_path'] or 'Direct profile (no YAML file)'}",
        f"Started: {_time(identity['created_at'])}",
        f'Last resumed: {_time(resumed)}',
        f'Latest recorded decision: {decision_text}',
        f'Last activity: {_time(latest)}',
        f"Status: {run['status']}", f'Stage: {stage}', f'Checkpoint: {phase}',
        f"Channels: {identity['channels']}", f"Operations: {identity['operations']}",
        f"Strategy: {identity['conversion_strategy']}", f'Folder: {directory}',
    ]
    return dict(run_id=directory.name, phase=run['current_phase'], latest=datetime.fromisoformat(latest),
                label=safe_value(label), details=[safe_value(line) for line in details])


def select_run(title, options, *, output_root=None, initial=None):
    """Select a filtered run with a wrapped detail panel for its highlighted entry."""
    from cli.interactive import select_option
    summaries = {}

    def details(value):
        if value not in summaries:
            directory = Path(output_root) / value if output_root else Path(value)
            summaries[value] = read_run_summary(directory)['details']
        return summaries[value]

    return select_option(title, options, heading='Migration runs', details=details,
                         filterable=True, initial=initial, empty_message='No matching runs')
