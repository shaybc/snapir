"""Diagnose conversion deliveries, candidates and reuse without changing saved runs."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.attempt_diagnostics import capture_attempts_for_run, attempt_scope, emit
from tools.run_diagnostics.conversion_ai import build_report, format_report
from tools.run_diagnostics.conversion_ai_export import export_conversion_report
from tools.run_diagnostics.report import diagnose
from tools.state_store_tools.behavior_units import initialize


@pytest.fixture
def run(tmp_path):
    root = tmp_path / 'saved-run'
    (root / 'state').mkdir(parents=True)
    with sqlite3.connect(root / 'state/migration.db') as conn:
        conn.execute('CREATE TABLE runs(run_id,status,current_phase)')
        conn.execute('INSERT INTO runs VALUES(?,?,?)', (root.name, 'in_progress', 'conversion_components_incomplete'))
        initialize(conn)
        conn.execute('CREATE TABLE conversion_component_plans(run_id,plan_json)')
        plan = dict(components={'string': dict(label='example.CCString', kind='java_implementation',
            roles=['format_leaf'], operations=['BANK/OpA','BANK/OpB'])},
            groups=[dict(group_id='string-group', members=['string'])])
        conn.execute('INSERT INTO conversion_component_plans VALUES(?,?)', (root.name, json.dumps(plan)))
    return root


def request():
    return dict(group_id='string-group', kind='basic_component',
        components={'string': dict(label='example.CCString', kind='java_implementation',
            roles=['format_leaf'], operations=['BANK/OpA','BANK/OpB'])},
        sources=[dict(identity='s', path='src/example/CCString.java', content='package example; class CCString {}')])


def add_attempt(run, number, response=None, error=None, category='component_generation', identity='string-group'):
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute('INSERT INTO behavior_attempts VALUES(?,?,?,?,?,?,?,?,?)',
            (run.name, category, identity, 'fingerprint', number, json.dumps(request()), response, error, f'2026-11-11T00:00:0{number}Z'))


def hashes(run):
    return {p.relative_to(run).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in run.rglob('*') if p.is_file()}


def test_conversion_history_skips_boundary_analysis_and_preserves_database(run, monkeypatch):
    add_attempt(run, 1, '<!DOCTYPE html><html>Failed to fetch response</html>', 'Invalid JSON')
    add_attempt(run, 2, r'{"content":"bad\q"}', 'Invalid JSON: invalid escape at line 17 column 784')
    add_attempt(run, 3, '{"files":[]}')
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute('INSERT INTO behavior_snapshots VALUES(?,?,?,?,?,?,?,?)',
            (run.name,'component_generation','string-group','fingerprint','accepted','{}',None,'now'))
    stage = run / 'reports/3_dependency_closure_and_component_conversion'
    stage.mkdir(parents=True)
    (stage / 'component-generation.json').write_text(json.dumps(dict(groups={'string-group':dict(status='component_validated',reused=False)})))
    monkeypatch.setattr('tools.run_diagnostics.report.class_evidence', lambda *_: pytest.fail('Ran earlier-stage investigation'))
    before = hashes(run)
    report = build_report(run)
    assert hashes(run) == before
    assert len(report.targets) == 1
    target = report.targets[0]
    assert target['type'] == 'basic format' and target['consumers'] == ['BANK/OpA','BANK/OpB']
    assert [a['outcome'] for a in target['attempts']] == ['html_or_upstream_error_content','invalid_json_escape','saved_validation_passed']
    assert target['attempts'][1]['parser_location'] == dict(line=17,column=784)
    text = '\n'.join(diagnose(run))
    assert 'basic format: example.CCString' in text and 'component validated (build/tests)' in text
    assert 'Boundary report missing' not in text and 'Boundaries:' not in text
    assert 'HTTP 200' in text  # Only the explicit limitation; no invented delivery status.
    assert not any(a['deliveries'] for a in target['attempts'])


def test_oversized_checks_are_not_transmitted_requests_and_missing_reports_do_not_block(run):
    from runtime.behavior_conversion.request_context import encode_request
    from runtime.behavior_conversion.oversized_request_capture import capture_for_run
    with capture_attempts_for_run(run), capture_for_run(run):
        with pytest.raises(ValueError, match='context budget'):
            encode_request(request(), 'instructions', 1)
    report = build_report(run)
    target = report.targets[0]
    assert len(target['budget_checks']) == 2
    assert not target['attempts']
    assert len(target['oversized_captures']) == 2
    assert 'NOT SENT' in '\n'.join(format_report(report))


def test_transport_retries_and_captured_materials_merge_into_one_generation_attempt(run, monkeypatch, tmp_path):
    monkeypatch.setattr('runtime.model_execution.adk_executor.require_model_readiness', lambda *_: None)
    calls = []
    executor = AdkExecutor(PipelineConfiguration(max_model_attempts=2))
    async def reply(*_):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError('503 upstream timeout api_key=secret-value')
        return '{"files":[]}'
    monkeypatch.setattr(executor, '_execute', reply)
    payload = json.dumps(request())
    with capture_attempts_for_run(run):
        with attempt_scope('component_generation','string-group','fingerprint',1) as trace:
            response = executor.execute('exact instructions', payload)
        emit('validation_passed', trace=trace, response=response)
    add_attempt(run, 1, response)
    report = build_report(run)
    target = report.targets[0]
    assert len(target['attempts']) == 1
    attempt = target['attempts'][0]
    assert [d['outcome'] for d in attempt['deliveries']] == ['timeout','response_received']
    assert all(d['http_status'] is None for d in attempt['deliveries'])
    assert attempt['outcome'] == 'saved_validation_passed'
    assert 'secret-value' not in (run / 'reports/model_attempts/events.jsonl').read_text()
    before = hashes(run)
    export_conversion_report(run, tmp_path, report)
    assert hashes(run) == before
    folder = tmp_path / 'work/diagnostics' / run.name
    exported = json.loads((folder / 'conversion-ai-summary.json').read_text())
    materials = exported['targets'][0]['attempts'][0]['materials']
    assert (folder / materials['instructions']['exported_file']).read_text() == 'exact instructions'
    assert (folder / materials['request']['exported_file']).read_text() == payload
    assert list(folder.glob('materials/*/sources/src/example/CCString.java'))
    delivery_error = exported['targets'][0]['attempts'][0]['deliveries'][0]['error_material']
    saved_error = (folder / delivery_error['exported_file']).read_text()
    assert 'upstream timeout' in saved_error and 'secret-value' not in saved_error


def test_captured_http_status_is_independent_of_invalid_response_content(run):
    import asyncio
    import httpx
    from runtime.model_execution.progress import response_headers
    from runtime.model_execution.attempt_diagnostics import delivery_scope
    with capture_attempts_for_run(run), attempt_scope('component_generation','string-group','f',1):
        emit('application_request', request=json.dumps(request()), instructions='instructions')
        with delivery_scope(1):
            asyncio.run(response_headers(httpx.Response(200,headers={'x-request-id':'gateway-123','x-api-key':'private-secret'})))
            emit('response_received', response='<html>upstream error</html>')
        emit('validation_failed', response='<html>upstream error</html>', error='Invalid JSON')
    target = build_report(run).targets[0]
    assert target['attempts'][0]['outcome'] == 'html_or_upstream_error_content'
    assert target['attempts'][0]['deliveries'][0]['http_status'] == 200
    assert target['attempts'][0]['deliveries'][0]['gateway_request_id'] == 'gateway-123'
    assert 'private-secret' not in (run / 'reports/model_attempts/events.jsonl').read_text()
    assert target['result'] == 'not established'


def test_staged_reservation_and_behavior_record_are_not_counted_twice(run):
    add_attempt(run, 1, '{}', 'schema validation error', category='staged_implementation', identity='string-group:rev')
    with sqlite3.connect(run / 'state/migration.db') as conn:
        from tools.state_store_tools.staged_conversion_state import initialize as staged_initialize
        staged_initialize(conn)
        conn.execute('INSERT INTO staged_conversion_attempts VALUES(?,?,?,?,?,?,?,?,?)',
            (run.name,'string-group','rev','implementation',1,json.dumps(request()),'{}','schema validation error','now'))
    report = build_report(run)
    assert sum(len(t['attempts']) for t in report.targets) == 1


def test_reuse_active_attempt_and_partial_journal_remain_distinct(run):
    add_attempt(run, 1)
    folder = run / 'reports/model_attempts'
    folder.mkdir(parents=True)
    (folder / 'events.jsonl').write_text('{"event":')
    stage = run / 'reports/3_dependency_closure_and_component_conversion'
    stage.mkdir(parents=True)
    (stage / 'component-generation.json').write_text(json.dumps(dict(groups={'reused-group':dict(status='component_validated',reused=True)})))
    report = build_report(run)
    assert report.targets[0]['attempts'][0]['outcome'] == 'in_progress_or_unknown'
    reused = next(t for t in report.targets if t['identity'] == 'reused-group')
    assert reused['result'] == 'reused validated component' and not reused['attempts']
    assert any('incomplete' in value for value in report.limitations)


@pytest.mark.parametrize('phase', ['planning_inputs_ready','unrecognized_phase'])
def test_other_stages_do_not_run_conversion_or_boundary_investigation(run, phase, monkeypatch):
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute('UPDATE runs SET current_phase=?',(phase,))
    monkeypatch.setattr('tools.run_diagnostics.report.class_evidence', lambda *_: pytest.fail('Earlier-stage investigation'))
    text = '\n'.join(diagnose(run))
    assert 'not applicable' in text and 'Boundaries:' not in text


def test_capture_io_failure_does_not_change_model_result(run, monkeypatch):
    import runtime.model_execution.attempt_diagnostics as capture
    monkeypatch.setattr(capture, '_blob', lambda *_: (_ for _ in ()).throw(OSError('read-only')))
    with capture_attempts_for_run(run), attempt_scope('component_generation','g'):
        emit('application_request', request='{}')
    assert not (run / 'reports/model_attempts/events.jsonl').exists()


def test_conversion_report_excludes_earlier_planning_calls(run):
    from runtime.model_execution.attempt_diagnostics import model_scope, delivery_scope
    with capture_attempts_for_run(run), model_scope('{"schema":{"title":"MigrationPlan"}}','planning instructions','Planning'):
        with delivery_scope(1):
            emit('response_received', response='{"plan":[]}')
    report = build_report(run)
    assert len(report.targets) == 1 and report.targets[0]['identity'] == 'string-group'
    assert not report.targets[0]['attempts']


def test_legacy_logs_require_an_explicit_target_label(run):
    logs = run / 'logs'
    logs.mkdir()
    (logs / 'model_execution.log').write_text('Model execution attempt 1/4 using model [Basic native group: example.CCString]\n'
        'Model attempt 1/4 failed: timeout [Basic native group: example.CCString]\n'
        'Model execution attempt 2/4 using model\n')
    report = build_report(run)
    target = report.targets[0]
    assert len(target['legacy_delivery_evidence']) == 2
    assert not target['attempts']
    assert any('unambiguous target label' in item for item in report.limitations)


def test_generation_capture_does_not_change_corrections_or_resume(run):
    from pydantic import BaseModel
    from types import SimpleNamespace
    from tools.state_store_tools.db import get_connection, create_all_tables
    from tools.state_store_tools.runs import upsert_run
    from runtime.behavior_conversion.generation import _generate
    class Result(BaseModel):
        value: int
    # Use a separate realistic run schema for the generation handoff.
    directory = run.parent / 'generation-run'
    (directory / 'state').mkdir(parents=True)
    conn = get_connection(str(directory / 'state/migration.db'))
    create_all_tables(conn)
    initialize(conn)
    upsert_run(conn, run_id=directory.name, run_mode='conversion', current_phase='conversion_pending')
    config = SimpleNamespace(run_id=directory.name)
    profile = PipelineConfiguration(model_provider='mock', max_agent_task_retries=2)
    calls = []
    def model(instruction, payload):
        calls.append(json.loads(payload))
        return r'{"value":"bad\q"}' if len(calls) == 1 else '{"value":1}'
    try:
        with capture_attempts_for_run(directory):
            value, _ = _generate(conn, config, profile, 'unit', 'unit-1', 'instructions',
                dict(unit_id='unit-1',kind='response_format'), Result, model_call=model, require_coverage=False)
        assert value.value == 1 and len(calls) == 2
        assert 'previous_model_response' in calls[1]
        assert conn.execute('SELECT count(*) FROM behavior_attempts').fetchone()[0] == 2
        report = build_report(directory)
        assert len(report.targets) == 1
        assert [a['outcome'] for a in report.targets[0]['attempts']] == ['invalid_json_escape','saved_validation_passed']
    finally:
        conn.close()


def test_captured_material_cannot_read_outside_the_run(run, tmp_path):
    from tools.run_diagnostics.ai_attempt_evidence import material_text
    outside = tmp_path / 'outside.txt'
    outside.write_text('not part of this run')
    reference = dict(storage='blob',path='../outside.txt',sha256=hashlib.sha256(outside.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match='leaves the selected run'):
        material_text(run, reference)


def test_active_operation_and_stale_head_do_not_claim_current_success(run):
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute('CREATE TABLE operation_workflow_progress(run_id,operation_key,status)')
        conn.execute('INSERT INTO operation_workflow_progress VALUES(?,?,?)',(run.name,'BANK/OpA','completed'))
        conn.execute('INSERT INTO operation_workflow_progress VALUES(?,?,?)',(run.name,'BANK/OpB','running'))
        conn.execute('CREATE TABLE conversion_component_heads(run_id,group_id,status)')
        conn.execute('INSERT INTO conversion_component_heads VALUES(?,?,?)',(run.name,'string-group','stale'))
    stage = run / 'reports/3_dependency_closure_and_component_conversion'
    stage.mkdir(parents=True)
    (stage / 'component-generation.json').write_text(json.dumps(dict(groups={'string-group':dict(status='component_validated')})))
    report = build_report(run)
    assert report.active_operation == 'BANK/OpB'
    assert report.targets[0]['result'] == 'stale (saved component head)'


def test_format_directions_are_taken_from_saved_lifecycle_evidence(run):
    payload = request()
    payload['format_lifecycles'] = {'string':[{'direction':'format'},{'direction':'unformat'}]}
    with capture_attempts_for_run(run), attempt_scope('component_generation','string-group'):
        emit('application_request', request=json.dumps(payload))
    target = build_report(run).targets[0]
    assert target['directions'] == ['format','unformat']


def test_historical_oversized_materials_export_without_new_journals(run, tmp_path):
    from runtime.behavior_conversion.oversized_request_capture import capture_for_run
    from runtime.behavior_conversion.request_context import encode_request
    with capture_for_run(run), pytest.raises(ValueError, match='context budget'):
        encode_request(request(), 'old exact instructions', 1)
    report = build_report(run)
    export_conversion_report(run, tmp_path, report)
    destination = tmp_path / 'work/diagnostics' / run.name
    summary = json.loads((destination / 'conversion-ai-summary.json').read_text())
    checks = summary['targets'][0]['budget_checks']
    assert len(checks) == 2 and not summary['targets'][0]['attempts']
    assert (destination / checks[0]['materials']['instructions']['exported_file']).read_text() == 'old exact instructions'


def test_diagnostic_cli_exports_current_conversion_report_without_boundary_requirements(run, tmp_path, monkeypatch, capsys):
    import importlib
    import sys
    command = importlib.import_module('tools.run_diagnostics.__main__')
    add_attempt(run, 1, '<html>error</html>', 'Invalid JSON')
    project = tmp_path / 'diagnostic-project'
    monkeypatch.setattr(command, '__file__', str(project / 'source/tools/run_diagnostics/__main__.py'))
    monkeypatch.setattr(sys, 'argv', ['diagnose-run', str(run)])
    before = hashes(run)
    command.main()
    assert hashes(run) == before
    text = capsys.readouterr().out
    assert 'HTML' in text.upper() and 'Conversion AI report:' in text
    assert 'Boundary report missing' not in text
    assert (project / 'work/diagnostics' / run.name / 'conversion-ai-summary.json').is_file()
    summary = json.loads((project / 'work/diagnostics' / run.name / 'conversion-ai-summary.json').read_text())
    error = summary['targets'][0]['attempts'][0]['materials']['error']
    assert (project / 'work/diagnostics' / run.name / error['exported_file']).read_text() == 'Invalid JSON'


def test_source_text_containing_html_or_status_numbers_is_not_a_transport_error():
    from tools.run_diagnostics.ai_response_findings import finding
    body = json.dumps({'content':'String page = "<html>401</html>";'})
    assert finding(body) == 'json_received_validation_unknown'
    assert finding(body, 'Invalid field latest_value at line 401 column 3') == 'candidate_validation_failed'
    assert finding(None, '') == 'failure_without_response'
    assert finding('{}', '') == 'candidate_validation_failed'


def test_empty_timeout_exception_keeps_its_delivery_failure_type(run, monkeypatch):
    monkeypatch.setattr('runtime.model_execution.adk_executor.require_model_readiness', lambda *_: None)
    executor = AdkExecutor(PipelineConfiguration(max_model_attempts=1))
    async def timeout(*_):
        raise TimeoutError()
    monkeypatch.setattr(executor, '_execute', timeout)
    with capture_attempts_for_run(run), attempt_scope('component_generation','string-group'):
        with pytest.raises(RuntimeError, match='TimeoutError'):
            executor.execute('instructions',json.dumps(request()))
    target = build_report(run).targets[0]
    assert target['attempts'][0]['deliveries'][0]['outcome'] == 'timeout'
    assert 'TimeoutError' in (run / 'reports/model_attempts/events.jsonl').read_text()


def test_underlying_analysis_failure_is_distinct_from_consequences(run):
    from tools.run_diagnostics.target_status import target_status, target_summary
    stage = run / 'reports/3_dependency_closure_and_component_conversion'
    stage.mkdir(parents=True)
    cause = dict(id='analysis-1', kind='boundary_analysis_inactivity', message='Converter boundary analysis inactivity timeout after 300 seconds without meaningful progress', output_bytes=123)
    groups = {
        'string-group': dict(status='incomplete', reason=cause['message'], root_cause_ids=['analysis-1'], failure_role='analysis_consequence'),
        'shared': dict(status='incomplete', reason='Required prerequisite blocked', root_cause_ids=['analysis-1'], failure_role='dependency_consequence'),
        'independent': dict(status='incomplete', reason='1 validation error for SharedFixtureBank')}
    (stage / 'component-generation.json').write_text(json.dumps(dict(analysis_failures=[cause], groups=groups)))
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute('CREATE TABLE conversion_component_heads(run_id,group_id,status)')
        conn.execute('INSERT INTO conversion_component_heads VALUES(?,?,?)', (run.name, 'string-group', 'component_validated'))
    before = hashes(run)
    result = build_report(run)
    assert result.analysis_failures == [cause]
    targets = {item['identity']: item for item in result.targets}
    assert target_status(targets['string-group']) == 'blocked'
    assert target_status(targets['shared']) == 'blocked'
    assert target_status(targets['independent']) == 'failed'
    assert 'analysis-1' in target_summary(targets['shared'])
    assert targets['string-group']['blocker'] == 'blocked_analysis_timeout'
    text = '\n'.join(format_report(result))
    assert 'Underlying analysis failure: analysis-1' in text
    assert 'Caused by (dependency_consequence): analysis-1' in text
    assert hashes(run) == before


def test_console_situation_exposes_saved_analysis_cause(run):
    from cli.workflow_situation import situation_lines
    stage = run / 'reports/3_dependency_closure_and_component_conversion'
    stage.mkdir(parents=True)
    (stage / 'component-generation.json').write_text(json.dumps(dict(
        analysis_failures=[dict(id='analysis-1', message='No meaningful analysis progress for 300 seconds')],
        groups={'string-group': dict(root_cause_ids=['analysis-1'])})))
    lines = situation_lines(run, 'blocked', 'conversion_components_incomplete', [], 'Resume after fixing the problem')
    assert any('Underlying analysis failure: No meaningful analysis progress' in line for line in lines)
    assert any('1 linked component/dependency consequences' in line for line in lines)
