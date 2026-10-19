"""Run one bounded live bank verification pass and preserve its exact stopping point.

Uses isolated run/registry/profile files. Never changes generated code, weakens
validation or repeats failed conversion jobs. Controlled fixture tests run separately.
"""

import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'source'))
from runtime.configuration import load_configuration
from runtime.model_execution.error_details import sanitize_diagnostic

OPERATIONS = ['GetClientLinksOp', 'ValidateClientLinksOp', 'GetClientOverviewOp']


def inspect_run(directory):
    """Read actual persisted run/progress without asserting successful conversion."""
    database = directory / 'state/migration.db'
    if not database.is_file():
        return dict(status='not_created', current_phase=None, operations=[])
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT status,current_phase FROM runs WHERE run_id=?', (directory.name,)).fetchone()
        progress = []
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='operation_workflow_progress'").fetchone():
            progress = [dict(item) for item in conn.execute(
                'SELECT operation_key,status,phase FROM operation_workflow_progress WHERE run_id=? ORDER BY position', (directory.name,))]
        return dict(row) | dict(operations=progress) if row else dict(status='not_created', operations=[])


def run_command(command, log_path, deadline):
    """Execute one CLI command; retain output and stop its process tree on timeout."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return dict(exit_code=None, timed_out=True, error='Verification time budget exhausted')
    environment = os.environ.copy()
    environment.update(PYTHONPATH=str(ROOT / 'source'), PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    with log_path.open('w', encoding='utf-8') as output:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=remaining)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, check=False)
            else:
                process.kill()
            process.wait(timeout=15)
            code = process.returncode
    text = log_path.read_text(encoding='utf-8', errors='replace')
    errors = [line for line in text.splitlines() if line.startswith('Migration error:')]
    return dict(exit_code=code, timed_out=timed_out,
                error=sanitize_diagnostic(errors[-1]) if errors else 'Verification time budget exhausted' if timed_out else None,
                log=str(log_path.relative_to(ROOT)))


def verify_run(folder, profile, name, deadline):
    """Run fresh intake once and Resume once; never retry a failed generation job."""
    import yaml
    path = folder / (name + '.yaml')
    path.write_text(yaml.safe_dump(profile.model_dump(mode='json')), encoding='utf-8')
    run_id = name + '-' + folder.name.rsplit('-', 1)[-1]
    directory = Path(profile.output_root) / run_id
    commands = []
    for command in ('start', 'resume'):
        result = run_command([sys.executable, '-m', 'cli', command, '--config', str(path), '--run-id', run_id],
                             folder / (name + '-' + command + '.log'), deadline)
        commands.append(dict(command=command, **result))
        if result['timed_out']:
            pause_interrupted_run(directory)
        state = inspect_run(directory)
        if result['exit_code'] != 0 or result['timed_out'] or (command == 'start' and state.get('current_phase') != 'conversion_plan_approved'):
            break
    return dict(run=str(directory.relative_to(ROOT)), commands=commands, **inspect_run(directory))


def pause_interrupted_run(directory):
    """Mark an owned, stopped verification run paused while preserving accepted work."""
    from tools.state_store_tools.db import get_connection
    from tools.state_store_tools.runs import get_run, update_run_status
    from tools.state_store_tools.operation_progress import active_operation, save_progress
    database = directory / 'state/migration.db'
    if not database.is_file():
        return
    conn = get_connection(str(database))
    try:
        run = get_run(conn, directory.name)
        if run and run['status'] in {'in_progress', 'started'}:
            current = active_operation(conn, directory.name)
            if current and current['status'] == 'running':
                save_progress(conn, directory.name, current['operation_key'], 'paused', run['current_phase'])
            update_run_status(conn, directory.name, 'paused', run['current_phase'])
    finally:
        conn.close()


def main():
    """Verify the real chain and attempt a second-job API-reuse check only after success."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=480)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error('seconds must be positive')
    suffix = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    folder = ROOT / 'work/stage-five-validation' / ('live-' + suffix)
    folder.mkdir(parents=True)
    import yaml
    profile = load_configuration(ROOT / 'configs/bank_operation_calls_validation.yaml')
    profile = profile.model_copy(update=dict(output_root=str(folder / 'runs'),
        service_registry_path=str(folder / 'registry/services.db'), source_workspace_id='bank-stage-five-' + suffix,
        plan_approval_policy='automatic', gate_policies={str(number): 'automatic' for number in range(1,5)},
        deployment_template_dir=str(ROOT / 'source/templates/deployment'),
        deployment_values={'INTERNET/' + operation: dict(image_name='localhost/verification/' + operation.lower() + ':stage-five')
                           for operation in OPERATIONS}, runtime_validation_mode='disabled', max_model_attempts=1))
    deadline = time.monotonic() + args.seconds
    report = dict(budget_seconds=args.seconds, dummy_runtime_validation=False, deployment_performed=False,
                  live_http_verification=False, second_run=None)
    report['chain_run'] = verify_run(folder, profile, 'chain', deadline)
    if report['chain_run'].get('status') == 'completed':
        second = profile.model_copy(update={'include_operations': ['ValidateClientLinksOp']})
        report['second_run'] = verify_run(folder, second, 'reuse', deadline)
        second_path = ROOT / report['second_run']['run'] / 'state/migration.db'
        if second_path.is_file():
            with sqlite3.connect(second_path.as_uri() + '?mode=ro', uri=True) as conn:
                preflight = conn.execute('SELECT report_json FROM operation_dependency_preflights').fetchone()
                report['second_run']['reused_operations'] = sorted(json.loads(preflight[0])['reused_services']) if preflight else []
    report['result'] = 'passed' if report['chain_run'].get('status') == 'completed' and report['second_run'] and report['second_run'].get('status') == 'completed' else 'blocked'
    (folder / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['# Stage five live bank verification', '', '**Result: ' + report['result'] + '**', '',
             'No dummy runtime validation, image publication or cluster deployment was performed.',
             'This run does not claim live HTTP verification.', '']
    for label in ('chain_run', 'second_run'):
        value = report[label]
        if value is None:
            lines.append('- Separate live reuse run was not started because the prerequisite conversion did not finish.')
            continue
        lines.extend(['## ' + label.replace('_', ' '), '', '- Status: ' + str(value.get('status')),
                      '- Checkpoint: ' + str(value.get('current_phase')), '- Run: ' + value['run']])
        lines.extend('- ' + item['operation_key'] + ': ' + item['status'] + ' / ' + item['phase'] for item in value['operations'])
        lines.extend('- ' + item['error'] for item in value['commands'] if item.get('error'))
    (folder / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(dict(report=str((folder / 'report.md').relative_to(ROOT)), result=report['result'],
                          chain_status=report['chain_run'].get('status'), checkpoint=report['chain_run'].get('current_phase'))))
    return 0 if report['result'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
