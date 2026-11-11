"""Verify offline investigation correlates saved evidence without mutations or secrets."""

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from tools.run_diagnostics.prepared_units import read_prepared_units
from tools.run_diagnostics.report import database, diagnose, issue_summary


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')


@pytest.fixture
def saved(tmp_path):
    run = tmp_path / 'run'
    state = run / 'state'
    state.mkdir(parents=True)
    vault = tmp_path / 'separate-map'
    analysis = vault / 'analysis/analysis.sqlite'
    analysis.parent.mkdir(parents=True)
    with sqlite3.connect(state / 'migration.db') as conn:
        conn.executescript('CREATE TABLE runs(run_id,status,current_phase,run_config_json);'
            'CREATE TABLE scoped_source_definitions(run_id,kind,logical_id);')
        conn.execute('INSERT INTO runs VALUES (?,?,?,?)', ('run', 'blocked', 'conversion_scoped_prepared',
            json.dumps(dict(vault_root=str(vault)))))
        conn.execute('INSERT INTO scoped_source_definitions VALUES (?,?,?)', ('run', 'java_class', 'example.Work'))
    with sqlite3.connect(analysis) as conn:
        conn.executescript('CREATE TABLE java_sources(file,fqcn); CREATE TABLE java_facts(file);'
            'CREATE TABLE notes(definition,source_relative_path,source_selector);'
            'CREATE TABLE files(path,relative_path); CREATE TABLE xml_nodes(id,file,selector);'
            'CREATE TABLE xml_attributes(node,name,value);')
        conn.execute('INSERT INTO java_sources VALUES (?,?)', ('/src/Work.java', 'example.Work'))
        conn.execute('INSERT INTO java_facts VALUES (?)', ('/src/Work.java',))
        conn.execute('INSERT INTO notes VALUES (?,?,?)', ('step', 'Operation.xml', '/opStep[1]'))
        conn.execute('INSERT INTO files VALUES (?,?)', ('/src/Operation.xml', 'Operation.xml'))
        conn.execute('INSERT INTO xml_nodes VALUES (?,?,?)', ('node', '/src/Operation.xml', '/opStep[1]'))
        conn.execute('INSERT INTO xml_attributes VALUES (?,?,?)', ('node', 'implClass', 'example.Work'))
    write_json(state / 'profile.json', dict(password='privateSettingValue'))
    stage = run / 'reports/3_dependency_closure_and_component_conversion'
    boundary = dict(kind='configured_step', implementation_class=None, analysis_status='verification_incomplete',
        issues=['Configured step has no evidenced implementation binding'])
    write_json(stage / 'behavior_verification_boundaries.json', dict(boundaries={'unit-1': boundary}))
    unit = dict(unit_id='unit-1', kind='configured_step', logical_id='OperationFailed', source_definition_id='step',
        effective_configuration=dict(attributes=dict(id='OperationFailed'), resolved_implementation='example.Work'),
        sources=[dict(content='privateSourceValue' * 20000)], service_connections=[dict(password='privateConnectorValue')])
    write_json(stage / 'scoped_workflow_preparation.json', dict(operations={'BANK/Op': dict(units=[unit])}))
    write_json(stage / 'component-generation.json', dict(groups={'group': dict(status='incomplete', members=['component'],
        reason='Component has no parser-backed entry points: example.Work')}))
    logs = run / 'logs'
    logs.mkdir()
    (logs / 'run.log').write_text('WARNING Component has no parser-backed entry points: example.Work privateLogValue\n')
    return run, stage, analysis


def test_saved_binding_and_index_are_correlated_without_reading_sources_or_changing_files(saved, monkeypatch):
    run, _, analysis = saved
    paths = [path for path in run.parent.rglob('*') if path.is_file()]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    original = Path.open
    def guard(path, *args, **kwargs):
        if path.suffix == '.java' or path.name.lower().startswith('dseconnector'):
            pytest.fail('Diagnostic opened source or deployment connector')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guard)
    output = '\n'.join(diagnose(run))
    assert 'Saved binding exists but boundary did not retain it' in output
    assert 'indexed=1; intake=1; indexing records=1' in output
    assert 'Related warnings in saved logs: 1' in output
    assert all(value not in output for value in ('privateSettingValue', 'privateSourceValue', 'privateConnectorValue', 'privateLogValue'))
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths} == before
    assert {path for path in run.parent.rglob('*') if path.is_file()} == set(paths)


def test_map_attribute_can_identify_a_missing_preparation_binding(saved):
    run, stage, _ = saved
    document = json.loads((stage / 'scoped_workflow_preparation.json').read_text())
    del document['operations']['BANK/Op']['units'][0]['effective_configuration']['resolved_implementation']
    write_json(stage / 'scoped_workflow_preparation.json', document)
    assert 'Map captured implClass but prepared binding is missing: example.Work' in '\n'.join(diagnose(run))


def test_diagnostic_prints_complete_saved_analyzer_issues(saved):
    run, stage, _ = saved
    path = stage / 'behavior_verification_boundaries.json'
    document = json.loads(path.read_text())
    boundary = document['boundaries']['unit-1']
    boundary['implementation_class'] = 'example.Work'
    boundary['issues'] = [
        'Converter boundary analysis could not finish: timed out after 180 seconds\nJava command details',
        'Additional analyzer detail ' + 'x' * 500,
    ]
    write_json(path, document)
    output = '\n'.join(diagnose(run))
    assert 'Finding: Java analyzer could not finish (launch failure or timeout)' in output
    for issue in boundary['issues']:
        for line in issue.splitlines():
            assert '      ' + line in output


@pytest.mark.parametrize('issue, expected', [
    ('Build the converter analysis tool: mvn package', 'analysis JAR is missing'),
    ('UnsolvedSymbolException: Unsolved symbol : vendor.Context', 'vendor.Context'),
    ('Entry method must resolve uniquely: example.Work.execute (matches=0)', 'No unique method'),
    ('Invalid Java source privateSourceValue', 'rejected supplied Java syntax'),
    ('Unknown problem password=privateSettingValue', 'see saved issue details'),
    ('Converter boundary analysis timed out after 300 seconds; last progress: loading JAR', 'exceeded its total runtime limit'),
    ('Boundary analyzer JAR lacks project classpath support; rebuild analyzer', 'Analyzer JAR is outdated'),
    ('Boundary JAR missing, unreadable or invalid for project BANK: C:/libs/driver.jar', 'C:/libs/driver.jar'),
])
def test_analyzer_findings_are_classified_without_raw_private_details(issue, expected):
    summary = issue_summary([issue])
    assert expected in summary
    assert 'private' not in summary


def test_streaming_reader_handles_escapes_and_does_not_keep_embedded_sources(tmp_path):
    path = tmp_path / 'prepared.json'
    unit = dict(unit_id='wanted', effective_configuration=dict(attributes=dict(id='A"B\\C')),
        sources=[dict(content='private source \"\\\n' * 100000)])
    write_json(path, dict(operations={'Op': dict(units=[unit, unit])}))
    found = read_prepared_units(path, {'wanted'})
    assert found['wanted']['effective_configuration']['attributes']['id'] == 'A"B\\C'
    assert 'sources' not in found['wanted']
    assert len(json.dumps(found)) < 500


def test_conflicting_repeated_unit_records_are_not_silently_selected(tmp_path):
    path = tmp_path / 'prepared.json'
    write_json(path, dict(units=[dict(unit_id='u', effective_configuration=dict(resolved_implementation='A')),
                                dict(unit_id='u', effective_configuration=dict(resolved_implementation='B'))]))
    with pytest.raises(ValueError, match='Conflicting'):
        read_prepared_units(path, {'u'})


def test_sqlite_connection_rejects_writes_and_missing_database(saved):
    run, _, _ = saved
    conn = database(run / 'state/migration.db')
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('DELETE FROM runs')
    finally:
        conn.close()
    with pytest.raises(sqlite3.OperationalError):
        database(run / 'missing.db')
    assert not (run / 'missing.db').exists()


def test_missing_or_truncated_reports_produce_a_short_limitation(saved):
    run, stage, _ = saved
    (stage / 'scoped_workflow_preparation.json').write_text('{"operations":')
    assert 'Preparation report missing, incomplete, or incompatible.' in diagnose(run)
    (stage / 'behavior_verification_boundaries.json').unlink()
    assert len(diagnose(run)) < 6


def test_command_entry_prints_a_short_report_for_the_selected_run(saved, monkeypatch, capsys):
    import sys
    from tools.run_diagnostics.__main__ import main
    run, _, _ = saved
    monkeypatch.setattr(sys, 'argv', ['diagnose-run', str(run)])
    main()
    output = capsys.readouterr().out
    assert 'SAVED RUN DIAGNOSTIC (read-only)' in output
    assert 'Saved binding exists' in output
    assert len(output.splitlines()) < 25


def test_numbered_selection_uses_existing_roots_without_filtering_failed_checkpoints(saved, monkeypatch, capsys):
    import sys
    from tools.run_diagnostics.__main__ import main
    run, _, _ = saved
    monkeypatch.setattr(sys, 'argv', ['diagnose-run'])
    monkeypatch.setattr('cli.status_discovery.discover_run_roots', lambda project: [run.parent])
    monkeypatch.setattr('builtins.input', lambda message: '')
    main()
    assert 'conversion_scoped_prepared' in capsys.readouterr().out
