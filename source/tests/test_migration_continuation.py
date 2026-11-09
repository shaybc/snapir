"""Continue default full migrations once, retaining real stop conditions and saved checkpoints."""

import sqlite3
from types import SimpleNamespace
import pytest
from runtime.migration_start import continue_after_intake


def run_directory(tmp_path, status='paused', phase='scoped_inventory_ready'):
    directory = tmp_path / 'runs' / 'example'
    (directory / 'state').mkdir(parents=True)
    with sqlite3.connect(directory / 'state/migration.db') as conn:
        conn.execute('CREATE TABLE runs(run_id TEXT,status TEXT,current_phase TEXT)')
        conn.execute('INSERT INTO runs VALUES (?,?,?)', (directory.name, status, phase))
    return directory


def test_full_start_calls_existing_resume_and_preserves_its_gate_stop(tmp_path, monkeypatch):
    directory = run_directory(tmp_path)
    calls = []
    def resume(root, name):
        calls.append((root, name))
        with sqlite3.connect(directory / 'state/migration.db') as conn:
            conn.execute("UPDATE runs SET current_phase='conversion_plan_pending'")
        return directory
    monkeypatch.setattr('runtime.checkpoints.resume_pipeline', resume)
    profile = SimpleNamespace(conversion_strategy='behavior_units', scoped_native_mode='component_first_v1')
    assert continue_after_intake(profile, directory) == directory
    assert calls == [(str(directory.parent), directory.name)]
    assert continue_after_intake(profile, directory) == directory
    assert len(calls) == 1  # A required approval is not bypassed by another continuation attempt.


@pytest.mark.parametrize('mode,status,phase', [
    ('prepare', 'paused', 'scoped_inventory_ready'),
    ('component_first_v1', 'blocked', 'dependency_preflight_blocked'),
    ('component_first_v1', 'failed', 'intake_failed'),
])
def test_prepare_only_or_blocked_intake_does_not_continue(tmp_path, monkeypatch, mode, status, phase):
    directory = run_directory(tmp_path, status, phase)
    monkeypatch.setattr('runtime.checkpoints.resume_pipeline', lambda *_: pytest.fail('Unexpected continuation'))
    profile = SimpleNamespace(conversion_strategy='behavior_units', scoped_native_mode=mode)
    assert continue_after_intake(profile, directory) == directory


def test_public_pipeline_continues_only_after_intake_returns(tmp_path, monkeypatch):
    from runtime import pipeline_runner
    directory = run_directory(tmp_path)
    profile = SimpleNamespace(conversion_strategy='behavior_units', scoped_native_mode='component_first_v1')
    events = []
    monkeypatch.setattr(pipeline_runner, '_run_intake', lambda *args: events.append('intake') or directory)
    monkeypatch.setattr('runtime.checkpoints.resume_pipeline', lambda *args: events.append('resume') or directory)
    assert pipeline_runner.run_pipeline(profile, 'example') == directory
    assert events == ['intake', 'resume']
