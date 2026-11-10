"""Keep measured preparation evidence separate from native conversion acceptance."""

import json
import sqlite3
from types import SimpleNamespace

import pytest

from runtime.scoped_acceptance import preparation_acceptance, process_peak_memory
from runtime.workspace_paths import run_report_path
from tools.composer_mapper_tools.scoped_context_state import SCOPED_CONTEXT_SCHEMA
from tools.composer_mapper_tools.scoped_vault_importer import SCOPED_SCHEMA
from test_behavior_verification_boundaries import boundary_tool


@pytest.fixture
def inventory(monkeypatch):
    # Measurement tests use synthetic rows, not a mapped vault for boundary discovery.
    monkeypatch.setattr('runtime.behavior_verification_boundaries.write_boundary_report', lambda *args, **kwargs: None)
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
        operations={'XML/Flow': {'status': 'prepared'}}, reused_contexts=['XML/Flow'],
        dependency_plan=dict(required_operations=['XML/Flow', 'WEB/B'], reused_services={'WEB/B': {}})), 1.25)
    assert result['counts'] == dict(source_definitions=1, entity_usages=0, operation_contexts=2,
        context_bindings=0, selected_contexts=1, attempted_contexts=1, prepared_contexts=1,
        blocked_contexts=0, reused_contexts=1, required_contexts=2, reused_services=1)
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
    assert statuses == [('blocked', 'conversion_scoped_gated') if failure else ('paused', 'conversion_scoped_prepared')]


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


def test_reused_preparation_rebuilds_boundary_with_saved_implementation(inventory, tmp_path, monkeypatch, boundary_tool):
    import runtime.scoped_conversion as runtime
    from test_behavior_verification_boundaries import unit, prepared
    from tools.behavior_verification.boundaries import build_boundary_report
    from runtime.workspace_paths import write_run_report
    value = unit()
    value['effective_configuration'] = dict(attributes={'id': 'OperationFailed', 'onOtherDo': 'end'},
        resolved_implementation='example.Work', implementation_mapping_key='OperationFailed')
    preparation = prepared(value)
    preparation['reused_contexts'] = ['XML/Flow']
    monkeypatch.setattr(runtime, 'prepare_scoped_workflow', lambda *args, **kwargs: preparation)
    monkeypatch.setattr(runtime, 'update_run_status', lambda *args: None)
    monkeypatch.setattr('tools.composer_mapper_tools.vault_importer.import_vault',
        lambda *args, **kwargs: pytest.fail('Resume must not repeat intake'))
    calls = []
    def discover(conn, config, report, directory, **options):
        options.pop('profile', None)
        boundary = build_boundary_report(report, tool_jar=boundary_tool, **options)
        calls.append(boundary)
        write_run_report(directory, 'behavior_verification_boundaries.json', json.dumps(boundary))
    monkeypatch.setattr('runtime.behavior_verification_boundaries.write_boundary_report', discover)
    write_run_report(tmp_path, 'behavior_verification_boundaries.json', json.dumps(dict(counts=dict(identified=0))))
    for _ in range(2):
        runtime.prepare_scoped_runtime(inventory, SimpleNamespace(run_id='run'), None, tmp_path)
        report = json.loads(run_report_path(tmp_path, 'behavior_verification_boundaries.json').read_text())
        assert report['counts']['identified'] == 1
        boundary = next(iter(report['boundaries'].values()))
        assert boundary['implementation_class'] == 'example.Work'
    assert len(calls) == 2
