"""Share the saved stage checklist between console and offline diagnostics."""
import sqlite3

from runtime.workflow_stages import STAGES, workflow_stage
from runtime.workspace_paths import run_database_path


def stage_rows(directory, status, phase, *, approved_three=False):
    """Read stage markers without advancing the migration or creating a database."""
    current = list(STAGES).index(workflow_stage(phase))
    completed = phase in {'migration_approved', 'dry_run_complete'}
    stages = []
    for index, (key, label) in enumerate(STAGES.items()):
        if index < current or completed:
            marker, description = '[V]', 'completed'
            if index == 1 and phase.startswith('conversion_scoped_'):
                # Preparation can stop before a migration plan has ever been created.
                try:
                    with sqlite3.connect(run_database_path(directory).as_uri() + '?mode=ro', uri=True) as state:
                        planned = state.execute('SELECT 1 FROM migration_plans WHERE run_id=? LIMIT 1', (directory.name,)).fetchone()
                except sqlite3.Error:
                    planned = None
                if not planned:
                    marker, description = '[ ]', 'not yet completed'
        elif index > current:
            marker, description = '[ ]', 'pending'
        else:
            marker = '!' if status in {'blocked', 'failed', 'stopped'} else '→'
            description = status if status in {'blocked', 'failed', 'stopped', 'in_progress'} else 'waiting'
            if phase == 'planning_inputs_ready' and status == 'paused':
                description = 'ready to start'
            if approved_three:
                description = 'waiting for resume'
        stages.append(dict(key=key, label=label, marker=marker, status=description, current=index == current))
    return stages


def progress_snapshot(directory):
    """Return the console's checkpoint guidance and operation-scoped saved progress."""
    from cli.workflow_progress import _gate_decision, checkpoint_guidance
    from cli.workflow_subsections import active_subsections
    from tools.state_store_tools.operation_progress import progress_rows
    with sqlite3.connect(run_database_path(directory).as_uri() + '?mode=ro', uri=True) as state:
        state.row_factory = sqlite3.Row
        row = state.execute('SELECT status,current_phase FROM runs WHERE run_id=?', (directory.name,)).fetchone()
        if row is None:
            raise ValueError('Saved run not found')
        status, phase = row['status'], row['current_phase'] or ''
        try:
            operations = [dict(item) for item in progress_rows(state, directory.name)]
        except sqlite3.Error:
            operations = []
        approved = phase == 'gate_3_pending' and status == 'paused' and _gate_decision(directory, '3') == 'approved'
        if approved:
            phase = 'service_generation_pending'
        try:
            subsections = active_subsections(state, directory, status, phase) if not operations else []
        except (sqlite3.Error, OSError, ValueError):
            subsections = []
        if approved:
            subsections = [(key, title.removesuffix(' (checkpoint detail unavailable)') + ' (waiting for Resume)'
                            if value == 'current' else title, value, children)
                           for key, title, value, children in subsections]
    details, next_step = checkpoint_guidance(directory, status, phase)
    if approved:
        details = ['Gate 3 approved; service generation is waiting for Resume']
        next_step = 'Resume this run to start service generation and validation.'
    return dict(status=status, checkpoint=row['current_phase'], stages=stage_rows(directory, status, phase, approved_three=approved),
                operations=operations, subsections=subsections, details=details, next_step=next_step,
                scope='Current operation workflow progress' if operations and phase not in {'migration_approved', 'dry_run_complete'} else 'Migration progress')
