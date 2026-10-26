"""Keep measured preparation evidence separate from native conversion acceptance."""

import json
import sqlite3
from types import SimpleNamespace

import pytest

from runtime.scoped_acceptance import preparation_acceptance, process_peak_memory
from runtime.workspace_paths import run_report_path
from tools.composer_mapper_tools.scoped_context_state import SCOPED_CONTEXT_SCHEMA
from tools.composer_mapper_tools.scoped_vault_importer import SCOPED_SCHEMA


@pytest.fixture
def inventory():
    conn = sqlite3.connect(':memory:')
    for statement in SCOPED_SCHEMA + SCOPED_CONTEXT_SCHEMA:
        conn.execute(statement)
    conn.execute("INSERT INTO scoped_source_definitions VALUES ('run','def','operation','Flow','hash','{}')")
    for run, identity, selected in (('run', 'a', 1), ('run', 'b', 0), ('other', 'a', 1)):
        conn.execute('INSERT INTO scoped_operation_contexts VALUES (?,?,?,?,?,?,?,?)',
            (run, identity, identity, 'Flow', 'def', 'Flow.md', selected, '{}'))
    yield conn
    conn.close()


def test_counts_are_run_scoped_and_prepared_is_not_accepted(inventory, monkeypatch):
    monkeypatch.setattr('runtime.scoped_acceptance.process_peak_memory',
        lambda: dict(bytes=123, scope='process_lifetime_peak_rss', error=None))
    result = preparation_acceptance(inventory, 'run', dict(
        operations={'XML/Flow': {'status': 'prepared'}}, reused_contexts=['XML/Flow']), 1.25)
    assert result['counts'] == dict(source_definitions=1, entity_usages=0, operation_contexts=2,
        context_bindings=0, selected_contexts=1, attempted_contexts=1, prepared_contexts=1,
        blocked_contexts=0, reused_contexts=1)
    assert result['elapsed_seconds'] == 1.25
    assert result['peak_memory']['bytes'] == 123
    assert result['preparation_status'] == 'passed'
    assert not result['conversion_enabled'] and not result['acceptance_complete']
    assert len(result['unverified_gates']) == 3


@pytest.mark.parametrize('preparation', [
    {}, {'operations': {'XML/Flow': {'status': 'blocked'}}},
    {'operations': {'XML/Flow': {'status': 'unknown'}}},
    {'preparation_error': 'stale evidence', 'operations': {'XML/Flow': {'status': 'prepared'}}},
])
def test_missing_failed_and_incomplete_preparation_remains_blocked(inventory, preparation):
    assert preparation_acceptance(inventory, 'run', preparation, 0)['preparation_status'] == 'blocked'


def test_actual_process_memory_counter_has_explicit_units_and_scope():
    result = process_peak_memory()
    assert result['scope'] == 'process_lifetime_peak_rss'
    if result['error'] is None:
        assert isinstance(result['bytes'], int) and result['bytes'] > 0
    else:
        assert result['bytes'] is None


def test_unavailable_memory_counter_is_not_reported_as_zero(monkeypatch):
    import ctypes
    import runtime.scoped_acceptance as acceptance
    monkeypatch.setattr(acceptance, 'os', SimpleNamespace(name='nt'))
    def unavailable(*args, **kwargs):
        raise OSError('counter unavailable')
    monkeypatch.setattr(ctypes, 'WinDLL', unavailable, raising=False)
    result = process_peak_memory()
    assert result['bytes'] is None
    assert 'counter unavailable' in result['error']


@pytest.mark.parametrize('failure', [False, True])
def test_runtime_writes_measurement_and_retains_guard(inventory, tmp_path, monkeypatch, failure):
    import runtime.scoped_conversion as runtime
    statuses = []
    def prepare(*args, **kwargs):
        if failure:
            raise ValueError('stale input')
        return dict(operations={'XML/Flow': {'status': 'prepared'}}, conversion_enabled=False)
    monkeypatch.setattr(runtime, 'prepare_scoped_workflow', prepare)
    monkeypatch.setattr(runtime, 'update_run_status', lambda *args: statuses.append(args[2:]))
    config = SimpleNamespace(run_id='run')
    original = runtime.prepare_scoped_runtime(inventory, config, None, tmp_path)
    report = json.loads(run_report_path(tmp_path, 'scoped_acceptance.json').read_text())
    assert report['elapsed_seconds'] >= 0
    assert report['preparation_status'] == ('blocked' if failure else 'passed')
    assert not report['conversion_enabled'] and not report['acceptance_complete']
    assert json.loads(run_report_path(tmp_path, 'scoped_workflow_preparation.json').read_text()) == original
    assert statuses == [('blocked', 'conversion_scoped_gated')]


def test_stale_runtime_preserves_stale_status_in_acceptance_report(inventory, tmp_path, monkeypatch):
    import runtime.scoped_conversion as runtime
    from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale
    statuses = []
    def stale(*args, **kwargs):
        raise ScopedCheckpointStale({'XML/Flow': ['Changed source']})
    monkeypatch.setattr(runtime, 'prepare_scoped_workflow', stale)
    monkeypatch.setattr(runtime, 'update_run_status', lambda *args: statuses.append(args[2:]))
    result = runtime.prepare_scoped_runtime(inventory, SimpleNamespace(run_id='run'), None, tmp_path)
    assert result['stale_contexts'] == {'XML/Flow': ['Changed source']}
    report = json.loads(run_report_path(tmp_path, 'scoped_acceptance.json').read_text())
    assert report['preparation_status'] == 'blocked'
    assert report['preparation_error']
    assert statuses == [('blocked', 'conversion_scoped_stale')]
