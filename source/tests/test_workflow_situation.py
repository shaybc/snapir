"""Show actionable saved failures after the legend without modifying migration state."""

import json
import sqlite3

from cli.workflow_progress import display_workflow_progress
from tests.test_workflow_progress import make_run


def test_latest_stage_six_json_failure_is_explicit_after_legend(tmp_path, capsys):
    directory = make_run(tmp_path, 'service_generation_blocked', 'blocked')
    database = directory / 'state/migration.db'
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE service_generation_checkpoints (run_id TEXT, channel TEXT, operation_id TEXT, validation_json TEXT)')
        conn.execute('INSERT INTO service_generation_checkpoints VALUES (?,?,?,?)',
            (directory.name, 'INTERNET', 'TransferFundsOp', json.dumps({'error': 'Expecting property name enclosed in double quotes: line 49 column 6152 (char 8348)', 'build_passed': False})))
    before = database.read_bytes()
    display_workflow_progress(directory)
    text = capsys.readouterr().out
    assert text.index('Requires attention') < text.index('Current situation:')
    assert 'Current situation: Stage 6' in text and 'blocked.' in text
    assert 'Current problem: INTERNET/TransferFundsOp: Generated response contains invalid JSON:' in text
    assert 'Required action:' in text
    assert database.read_bytes() == before


def test_review_budget_failure_uses_recorded_exception_not_old_test_error(tmp_path, capsys):
    directory = make_run(tmp_path, 'assembly_pending', 'failed')
    logs = directory / 'logs'
    logs.mkdir()
    (logs / 'model_execution.log').write_text('ERROR Migration action failed\nValueError: Old test failure\nERROR Migration action failed\nTraceback:\nValueError: Behavior request exceeds its context budget; reduce the evidence unit or use incremental analysis\n', encoding='utf-8')
    display_workflow_progress(directory)
    text = capsys.readouterr().out
    assert 'Current problem: Behavior request exceeds its context budget' in text
    assert 'Old test failure' not in text


def test_waiting_run_does_not_display_historical_failure(tmp_path, capsys):
    directory = make_run(tmp_path, 'gate_3_pending')
    logs = directory / 'logs'
    logs.mkdir()
    (logs / 'model_execution.log').write_text('ERROR Migration action failed\nValueError: Old failure\n')
    display_workflow_progress(directory)
    text = capsys.readouterr().out
    assert 'Gate 3 awaiting review' in text
    assert 'Current problem:' not in text and 'Old failure' not in text


def test_missing_failure_evidence_is_reported_honestly(tmp_path, capsys):
    directory = make_run(tmp_path, 'service_generation_blocked', 'blocked')
    display_workflow_progress(directory)
    assert 'No detailed failure reason was saved' in capsys.readouterr().out


def test_saved_compiler_diagnostic_is_displayed_instead_of_generic_failure(tmp_path, capsys):
    directory = make_run(tmp_path, 'service_generation_blocked', 'blocked')
    with sqlite3.connect(directory / 'state/migration.db') as conn:
        conn.execute('CREATE TABLE service_generation_checkpoints (run_id TEXT, channel TEXT, operation_id TEXT, validation_json TEXT)')
        conn.execute('INSERT INTO service_generation_checkpoints VALUES (?,?,?,?)',
            (directory.name, 'WEB', 'Operation', json.dumps({'failure_class': 'build_failure', 'compile_failed': True,
                'compile_log': {'stdout': '[ERROR] Controller.java:[12,4] cannot find symbol\n', 'stderr': ''}})))
    display_workflow_progress(directory)
    assert 'Current problem: WEB/Operation: compile failed: Controller.java:[12,4] cannot find symbol' in capsys.readouterr().out
