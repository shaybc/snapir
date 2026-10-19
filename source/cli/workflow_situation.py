"""Explain the saved run's current state and failure before the interactive menu."""

import json
import re
import sqlite3

from runtime.workflow_stages import STAGES, workflow_stage
from runtime.workspace_paths import run_database_path, run_report_path


def _log_error(directory):
    """Read the last recorded action exception without loading model payloads."""
    path = directory / 'logs/model_execution.log'
    if not path.is_file():
        return None
    with path.open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 1024 * 1024))
        lines = stream.read().decode('utf-8', errors='replace').splitlines()
    start = next((index for index in range(len(lines) - 1, -1, -1)
                  if 'Migration action failed' in lines[index]), None)
    if start is None:
        return None
    if any('Workflow stage:' in line for line in lines[start + 1:]):
        return None
    for line in reversed(lines[start:]):
        match = re.match(r'^[\w.]+(?:Error|Exception):\s*(.+)', line)
        if match:
            return match[1]
    return None


def _saved_problem(directory, stage):
    """Select current-stage diagnostic evidence, not stale errors from earlier stages."""
    if stage == 'dependency_closure_and_component_conversion':
        try:
            with sqlite3.connect(run_database_path(directory).as_uri() + '?mode=ro', uri=True) as conn:
                row = conn.execute('SELECT current_phase FROM runs WHERE run_id=?', (directory.name,)).fetchone()
            if row and row[0] == 'conversion_service_connections_pending':
                questions = json.loads(run_report_path(directory, 'service_connection_questions.json').read_text())
                return 'Service/connector discovery needs a decision: ' + '; '.join(
                    item['channel'] + '/' + item['service_id'] + ': ' + ', '.join(item['issues']) for item in questions)
        except (OSError, ValueError, sqlite3.Error):
            pass
    if stage == 'service_generation_and_validation':
        try:
            with sqlite3.connect(run_database_path(directory).as_uri() + '?mode=ro', uri=True) as conn:
                rows = conn.execute('SELECT channel, operation_id, validation_json FROM service_generation_checkpoints WHERE run_id=?', (directory.name,)).fetchall()
            for channel, operation, encoded in rows:
                result = json.loads(encoded or '{}')
                if result.get('error'):
                    error = result['error']
                    if re.match(r'Expecting |Unterminated string|Invalid \\escape|Extra data', error):
                        error = 'Generated response contains invalid JSON: ' + error
                    return f'{channel}/{operation}: {error}'
                if result.get('failure_class'):
                    if result.get('wiring_feedback'):
                        return f"{channel}/{operation}: {result['wiring_feedback']}"
                    for goal in ('compile', 'test', 'package'):
                        if result.get(goal + '_failed'):
                            log = result.get(goal + '_log', {})
                            errors = [line.removeprefix('[ERROR]').strip() for line in log.get('stdout', '').splitlines()
                                      if line.startswith('[ERROR]') and line.removeprefix('[ERROR]').strip()]
                            if errors:
                                return f'{channel}/{operation}: {goal} failed: ' + '; '.join(errors[:3])
                    return f"{channel}/{operation}: {result['failure_class']}; inspect the stage validation report for diagnostics"
        except (sqlite3.Error, ValueError, TypeError):
            pass
    reports = {'final_validation': 'delivery_manifest.json'}
    if stage in reports:
        try:
            result = json.loads(run_report_path(directory, reports[stage]).read_text(encoding='utf-8'))
            if result.get('blockers'):
                return str(result['blockers'])
        except (OSError, ValueError):
            pass
    return _log_error(directory)


def situation_lines(directory, status, phase, details, next_step):
    """Return concise current-state, problem and action lines from read-only evidence."""
    stage = workflow_stage(phase)
    number = list(STAGES).index(stage) + 1
    blocked = status in {'failed', 'blocked', 'stopped'}
    needs_connection_decision = phase == 'conversion_service_connections_pending'
    if phase in {'migration_approved', 'dry_run_complete'}:
        situation = 'Migration completed.'
    else:
        state = status if blocked or status == 'in_progress' else 'waiting'
        situation = f'Stage {number} — {STAGES[stage]}: {state}. ' + '; '.join(details)
    lines = ['Current situation: ' + situation]
    if blocked or needs_connection_decision:
        problem = _saved_problem(directory, stage)
        if not problem:
            problem = 'No detailed failure reason was saved; inspect this run’s stage reports and logs.'
        problem = ' '.join(str(problem).split())
        lines.append('Current problem: ' + (problem if len(problem) <= 600 else problem[:597] + '...'))
    if needs_connection_decision:
        next_step = 'Resume to answer the grouped service/connector questions; supply missing workspace definitions before refreshing intake.'
    lines.append('Required action: ' + next_step)
    return lines
