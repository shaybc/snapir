"""Verify read-only traces separate raw requests from diagnostic projections."""
import hashlib
import json
import sqlite3

from tools.behavior_verification.format_lifecycle import basic_identity
from tools.run_diagnostics.format_flow_trace import extract_format_flow


def test_trace_preserves_mismatch_and_excludes_private_content(tmp_path):
    run = tmp_path / 'run-1'
    (run / 'state').mkdir(parents=True)
    reports = run / 'reports'
    reports.mkdir()
    name = 'example.CCString'
    component = dict(label=name, kind='java_implementation', roles=['format_leaf'], unit_ids=['unit-1', 'unit-2'])
    plan = dict(components={'string': component}, groups=[dict(group_id='group-1', members=['string'], dependencies=[])])
    request = dict(group_id='group-1', components={'string': component},
                   source_entry_points={'string': ['example.CCString.unformat(String,DataField)']},
                   sources=[{'content': 'PRIVATE_SOURCE'}], instructions='PRIVATE_PROMPT')
    receipt = dict(source_entry_points=request['source_entry_points'], validation_scope='build_and_tests',
                   validation={'status': 'passed', 'stdout': 'PRIVATE_LOG'})
    receipt_path = run / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt))
    artifact = dict(artifact_root=str(run), validation_report='receipt.json',
                    validation_report_hash=hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                    input_revision='input-1', contract_revision='contract-1')
    database = run / 'state/migration.db'
    with sqlite3.connect(database) as conn:
        conn.executescript('''CREATE TABLE runs(run_id TEXT);
            CREATE TABLE conversion_component_plans(run_id TEXT, plan_json TEXT, fingerprint TEXT);
            CREATE TABLE behavior_attempts(run_id TEXT,category TEXT,identity TEXT,fingerprint TEXT,attempt INTEGER,request_json TEXT,response TEXT,error TEXT);
            CREATE TABLE conversion_component_records(run_id TEXT,group_id TEXT,category TEXT,revision TEXT,record_json TEXT);''')
        conn.execute('INSERT INTO runs VALUES (?)', ('run-1',))
        conn.execute('INSERT INTO conversion_component_plans VALUES (?,?,?)', ('run-1', json.dumps(plan), 'plan-1'))
        conn.execute('INSERT INTO behavior_attempts VALUES (?,?,?,?,?,?,?,?)',
                     ('run-1', 'component_generation', 'group-1', 'fingerprint-1', 1, json.dumps(request), 'PRIVATE_RESPONSE', 'PRIVATE_ERROR'))
        sibling = dict(request, group_id='group-2')
        conn.execute('INSERT INTO behavior_attempts VALUES (?,?,?,?,?,?,?,?)',
                     ('run-1', 'component_generation', 'group-2', 'fingerprint-2', 1, json.dumps(sibling), None, None))
        conn.execute('INSERT INTO conversion_component_records VALUES (?,?,?,?,?)',
                     ('run-1', 'group-1', 'result', 'result-1', json.dumps({'results': {'string': artifact}})))
    boundary = dict(implementation_class=name, format_scope='basic', analysis_status='identified',
                    legacy_method={'declaring_class': name, 'signature': 'example.CCString.unformat(String,DataField)', 'excerpt': 'PRIVATE_SOURCE'})
    (reports / 'behavior_verification_boundaries.json').write_text(json.dumps(dict(
        basic_boundaries={basic_identity('unit-1', name): boundary}, boundaries={'unit-1': {'implementation_class': 'example.CCXML'}})))
    (reports / 'conversion-ai-summary.json').write_text(json.dumps({'targets': [dict(identity='group-1',
        source_entry_points={'string': ['example.CCXML.unformatContext(String,Context)']})]}))
    journal = reports / 'model_attempts'
    (journal / 'blobs').mkdir(parents=True)
    body = json.dumps(request).encode()
    hashed = hashlib.sha256(body).hexdigest()
    (journal / 'blobs' / (hashed + '.txt')).write_bytes(body)
    (journal / 'events.jsonl').write_text(json.dumps(dict(event='application_request', trace_id='trace-1',
        identity='group-1', request_blob=hashed)) + '\n' + json.dumps(dict(event='response_received', trace_id='trace-1',
        response='PRIVATE_RESPONSE')) + '\n')
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    result = extract_format_flow(run, name)
    text = json.dumps(result)
    assert 'PRIVATE_' not in text
    assert result['exact_boundary_lookups'][0]['found'] is True
    assert result['exact_boundary_lookups'][1]['found'] is False
    assert result['captured_requests'][0]['request_sha256'] == hashed
    assert len(result['delivery_timeline']) == 2
    assert result['database_attempts'][0]['request']['source_entry_points'] == request['source_entry_points']
    assert 'CCXML' in json.dumps(result['saved_diagnostics'])
    assert result['validation_receipts'][0]['checksum_matches'] is True
    assert result['validation_receipts'][0]['source_entry_points'] == request['source_entry_points']
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    exported = tmp_path / 'diagnostics'
    exported.mkdir()
    (exported / 'request.json').write_bytes(body)
    (exported / 'conversion-ai-summary.json').write_text(json.dumps({'targets': [dict(identity='group-1',
        attempts=[dict(identity='group-1', materials={'request': {'exported_file': 'request.json'}})])]}))
    separate = extract_format_flow(run, name, exported)
    assert separate['saved_diagnostics'][0]['attempts'][0]['request_sha256'] == hashed
    assert 'PRIVATE_' not in json.dumps(separate)
    exact = extract_format_flow(run, None, group_id='group-1')
    assert exact['group_id'] == 'group-1'
    assert len(exact['database_attempts']) == 1
    assert exact['database_attempts'][0]['identity'] == 'group-1'
    assert exact['exact_boundary_lookups'][0]['found'] is True
    other = extract_format_flow(run, None, group_id='group-2')
    assert len(other['database_attempts']) == 1
    assert other['database_attempts'][0]['identity'] == 'group-2'
    assert other['validation_receipts'] == []


def test_trace_exports_framework_metadata_without_source():
    from tools.run_diagnostics.format_flow_trace import _boundary
    value = _boundary(dict(implementation_class='example.CCString', analysis_status='identified',
        framework_boundaries=[dict(declaring_class='framework.FieldFormat', signature='framework.FieldFormat.format(Context)',
                                   path='PRIVATE_PATH', content='PRIVATE_SOURCE')]))
    assert value['framework_boundaries'][0]['declaring_class'] == 'framework.FieldFormat'
    assert 'PRIVATE_' not in json.dumps(value)


def test_cli_selects_exact_group_without_default_ccstring(monkeypatch, capsys):
    from tools.run_diagnostics import trace_format_flow
    calls = []
    def extract(*args, **kwargs):
        calls.append((args, kwargs))
        return {'group_id': kwargs['group_id']}
    monkeypatch.setattr(trace_format_flow, 'extract_format_flow', extract)
    monkeypatch.setattr('sys.argv', ['trace', '--run', 'saved-run', '--group', 'exact-group', '--diagnostics', 'saved-diagnostics'])
    assert trace_format_flow.main() == 0
    assert calls == [(('saved-run', None, 'saved-diagnostics'), {'group_id': 'exact-group'})]
    assert json.loads(capsys.readouterr().out) == {'group_id': 'exact-group'}
