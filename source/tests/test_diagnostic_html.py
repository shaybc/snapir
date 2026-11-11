"""Verify stage-scoped offline exports preserve state and distinguish saved evidence."""
import hashlib
import json
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys

import pytest

from cli.workflow_progress import display_workflow_progress
from cli.workflow_progress_snapshot import progress_snapshot
from models.conversion_ai_report import ConversionAiReport
from tools.run_diagnostics.conversion_ai_export import export_conversion_report
from tools.run_diagnostics.html_report import export_html_report
from tools.run_diagnostics.target_status import target_status


@pytest.fixture
def run(tmp_path):
    directory = tmp_path / 'run'
    (directory / 'state').mkdir(parents=True)
    with sqlite3.connect(directory / 'state/migration.db') as conn:
        conn.execute('CREATE TABLE runs(run_id,status,current_phase)')
        conn.execute('INSERT INTO runs VALUES(?,?,?)', ('run', 'blocked', 'conversion_components_incomplete'))
    return directory


def target(identity, **fields):
    return dict(identity=identity, name=identity, type='basic format', consumers=['BANK/Op'], directions=['format'],
                result=fields.pop('result', 'not established'), attempts=fields.pop('attempts', []),
                budget_checks=[], **fields)


def report(run, targets):
    return ConversionAiReport(run_id=run.name, status='blocked', checkpoint='conversion_components_incomplete',
        stage='dependency_closure_and_component_conversion', observed_at='2026-11-11T10:00:00Z', targets=targets)


def dashboard_data(root):
    body = (root / 'assets/report-data.js').read_text(encoding='utf-8')
    return json.loads(body.removeprefix('window.diagnosticReport = ').removesuffix(';\n'))


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def test_offline_export_links_exact_materials_and_preserves_state(run, tmp_path, capsys):
    evil = '</script><img src=x onerror=alert(1)>'
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute('CREATE TABLE behavior_attempts(run_id,response)')
        conn.execute('INSERT INTO behavior_attempts VALUES(?,?)', (run.name, evil))
    attempts = [dict(number=1, category='component_generation', outcome='invalid_json_syntax',
        error_summary=evil, deliveries=[dict(number=1, outcome='response_received', http_status=200)],
        materials=dict(response=dict(storage='database', table='behavior_attempts', column='response', rowid=1)))]
    items = [target('string', result='incomplete', blocker='blocked_entry_resolution', blocker_summary=evil, attempts=attempts),
        target('xml', result='incomplete', blocker='blocked_prerequisite', blocker_summary='Required native prerequisite: string', prerequisites=['string']),
        target('shared', result='reused validated component')]
    project = tmp_path / 'project'
    before = hashes(run)
    export_conversion_report(run, project, report(run, items))
    export_html_report(run, project, conversion=True)
    assert hashes(run) == before
    destination = project / 'work/diagnostics/run'
    data = dashboard_data(destination)
    assert data['counts'] == {'failed': 1, 'blocked': 1, 'completed': 1}
    assert data['targets'][0]['dependents'] == ['xml']
    assert data['targets'][1]['prerequisite_statuses'] == {'string': 'failed'}
    reference = data['targets'][0]['attempts'][0]['materials']['response']
    assert (destination / reference['href']).read_text() == evil
    assert data['targets'][0]['attempts'][0]['deliveries'][0]['http_status'] == 200
    assert evil not in (destination / 'assets/report-data.js').read_text()
    assert data['targets'][0]['summary'] == evil
    assert 'fetch(' not in (destination / 'assets/dashboard.js').read_text()
    assert 'innerHTML' not in (destination / 'assets/dashboard.js').read_text()
    assert 'https://' not in (destination / 'index.html').read_text(encoding='utf-8')
    display_workflow_progress(run)
    console = capsys.readouterr().out
    for index, stage in enumerate(data['progress']['stages'], 1):
        assert f"{index}. {stage['label']} ({stage['status'].upper()})" in console


@pytest.mark.parametrize('value,expected', [
    (target('a', result='external_policy'), 'external policy'),
    (target('a', result='configuration_verified'), 'completed'),
    (target('a', result='incomplete', blocker='blocked_prerequisite'), 'blocked'),
    (target('a', members=['a']), 'not started'),
    (target('a'), 'unknown'),
    (target('a', attempts=[dict(outcome='saved_validation_passed')]), 'validation recorded'),
    (target('a', result='component_validated', attempts=[dict(outcome='invalid_json_syntax')]), 'completed'),
    (target('a', attempts=[dict(outcome='in_progress_or_unknown')]), 'running or unknown'),
])
def test_status_does_not_invent_conversion_acceptance(value, expected):
    assert target_status(value) == expected


def test_stage_routing_exports_only_ai_materials_during_conversion(run, tmp_path, monkeypatch):
    from tools.run_diagnostics import __main__ as cli
    project = tmp_path / 'project'
    monkeypatch.setattr(sys, 'argv', ['diagnostics', str(run)])
    monkeypatch.setattr(cli, '__file__', str(project / 'source/tools/run_diagnostics/__main__.py'))
    monkeypatch.setattr('tools.run_diagnostics.conversion_ai.build_report', lambda *_: report(run, []))
    monkeypatch.setattr('tools.run_diagnostics.request_materials.export_request_materials',
                        lambda *_: pytest.fail('Legacy export was run during AI diagnosis'))
    monkeypatch.setattr(cli, 'diagnose', lambda *_: pytest.fail('Earlier-stage diagnosis ran'))
    old = project / 'work/diagnostics/run/old-hash/request.json'
    old.parent.mkdir(parents=True)
    old.write_text('old evidence')
    before = old.stat().st_mtime_ns
    cli.main()
    assert old.read_text() == 'old evidence' and old.stat().st_mtime_ns == before
    assert (old.parent.parent / 'index.html').is_file()
    assert dashboard_data(old.parent.parent)['files'] == [
        dict(path='conversion-ai-summary.json', href='conversion-ai-summary.json'),
        dict(path='conversion-ai-summary.txt', href='conversion-ai-summary.txt')]


@pytest.mark.parametrize('phase', ['planning_inputs_ready', 'gate_3_pending', 'migration_approved', 'conversion_scoped_prepared'])
def test_other_stages_keep_overview_without_running_ai_diagnosis(run, tmp_path, monkeypatch, phase):
    from tools.run_diagnostics import __main__ as cli
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute('UPDATE runs SET current_phase=?,status=?', (phase, 'paused'))
    project = tmp_path / 'project'
    monkeypatch.setattr(sys, 'argv', ['diagnostics', str(run)])
    monkeypatch.setattr(cli, '__file__', str(project / 'source/tools/run_diagnostics/__main__.py'))
    monkeypatch.setattr('tools.run_diagnostics.conversion_ai.build_report', lambda *_: pytest.fail('AI diagnosis ran at wrong stage'))
    monkeypatch.setattr('tools.run_diagnostics.request_materials.export_request_materials', lambda *_: [])
    cli.main()
    data = dashboard_data(project / 'work/diagnostics/run')
    assert not data['conversion'] and len(data['progress']['stages']) == 7
    assert data['targets'] == []


def test_saved_index_and_analysis_are_labelled_without_reading_source_files(run, tmp_path):
    intake = run / 'reports/1_intake_and_legacy_analysis'
    intake.mkdir(parents=True)
    (intake / 'java_source_index.json').write_text(json.dumps(dict(classes={'example.CCString': ['missing/CCString.java']})))
    stage = run / 'reports/3_dependency_closure_and_component_conversion'
    stage.mkdir(parents=True)
    (stage / 'behavior_verification_boundaries.json').write_text(json.dumps(dict(boundaries={'unit':dict(
        implementation_class='example.CCString', analysis_status='verification_incomplete', issues=['Entry method has no supplied Java source'])})))
    export_html_report(run, tmp_path / 'project', diagnostic_lines=['Saved diagnostic'])
    evidence = dashboard_data(tmp_path / 'project/work/diagnostics/run')['saved_evidence']
    assert evidence[0]['status'] == 'indexed'
    assert evidence[1]['status'] == 'verification_incomplete'
    assert evidence[1]['details']['issues'] == ['Entry method has no supplied Java source']
    assert not (run / 'missing').exists()


def test_preparation_does_not_falsely_mark_uncreated_plan_completed(run):
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute("UPDATE runs SET current_phase='conversion_scoped_prepared'")
    assert progress_snapshot(run)['stages'][1]['status'] == 'not yet completed'


def test_offline_dashboard_navigation_with_large_saved_history(run, tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the offline dashboard interaction test')
    intake = run / 'reports/1_intake_and_legacy_analysis'
    intake.mkdir(parents=True)
    (intake / 'java_source_index.json').write_text(json.dumps(dict(classes={'CCString': ['src/CCString.java']})))
    items = [target('CCString', result='incomplete', blocker='blocked_entry_resolution', blocker_summary='Entry method has no supplied Java source', members=['s']),
        target('CCXML', result='incomplete', blocker='blocked_prerequisite', blocker_summary='Required prerequisite: CCString', prerequisites=['CCString']),
        target('step', result='component_validated'), target('planned', members=['planned'])]
    items[0]['directions'] = ['unformat']
    items[2]['consumers'] = ['BANK/Other']
    items += [target(f'external-{number}', result='external_policy') for number in range(1250)]
    project = tmp_path / 'project'
    export_conversion_report(run, project, report(run, items))
    export_html_report(run, project, conversion=True)
    result = subprocess.run([node, str(Path(__file__).with_name('test_diagnostic_dashboard.cjs')),
        str(project / 'work/diagnostics/run/assets')], capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_dashboard_uses_saved_plan_dependencies_and_entry_evidence(run):
    from tools.run_diagnostics.conversion_ai import build_report
    plan = dict(components={'s': dict(label='CCString', kind='java_implementation', roles=['format_leaf']),
        'x': dict(label='CCXML', kind='java_implementation', roles=['format_wrapper'])},
        groups=[dict(group_id='string', members=['s'], dependencies=[]),
                dict(group_id='xml', members=['x'], dependencies=['string'])])
    request = dict(group_id='string', kind='basic_component', source_entry_points={'s': ['StringFormatHolder.formatField(DataField)']},
        format_lifecycles={'s': [dict(direction='format', declaring_class='example.StringFormatHolder')]})
    with sqlite3.connect(run / 'state/migration.db') as conn:
        conn.execute('CREATE TABLE conversion_component_plans(run_id,plan_json)')
        conn.execute('INSERT INTO conversion_component_plans VALUES(?,?)', (run.name, json.dumps(plan)))
        conn.execute('CREATE TABLE behavior_attempts(run_id,category,identity,fingerprint,attempt,request_json,response,error)')
        conn.execute('INSERT INTO behavior_attempts VALUES(?,?,?,?,?,?,?,?)',
            (run.name, 'component_generation', 'string', 'revision', 1, json.dumps(request), None, 'Entry method has no supplied Java source'))
    targets = {item['identity']: item for item in build_report(run).targets}
    assert targets['xml']['prerequisites'] == ['string']
    assert targets['string']['source_entry_points'] == request['source_entry_points']
    assert targets['string']['format_lifecycles'] == request['format_lifecycles']
    assert targets['string']['directions'] == ['format']


def test_material_links_cannot_escape_export_directory(tmp_path):
    from tools.run_diagnostics.html_report import _file_link
    destination = tmp_path / 'export'
    destination.mkdir()
    (tmp_path / 'outside.txt').write_text('outside')
    assert _file_link('../outside.txt', destination) is None
    assert _file_link(str(tmp_path / 'outside.txt'), destination) is None
    assert _file_link('missing.txt', destination) is None
