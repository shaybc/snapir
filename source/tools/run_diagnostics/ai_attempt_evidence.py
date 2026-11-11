"""Read conversion evidence from existing SQLite, reports and append-only captures."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3


def read_json(path, default=None):
    """Treat missing or partial reports as unavailable, never as successful results."""
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else default
    except (OSError, ValueError, RecursionError):
        return default


def rows(conn, table, run_id):
    """Read optional versioned tables without creating schemas or touching other runs."""
    allowed = {'behavior_attempts', 'behavior_snapshots', 'conversion_component_plans',
               'conversion_component_heads', 'shared_component_consumers', 'staged_conversion_attempts',
               'operation_workflow_progress'}
    if table not in allowed:
        raise ValueError('Unsupported diagnostic evidence table')
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return []
    required = {
        'behavior_attempts': {'category','identity','fingerprint','attempt','request_json','response','error'},
        'behavior_snapshots': {'category','identity','fingerprint','status'},
        'conversion_component_plans': {'plan_json'},
        'conversion_component_heads': {'group_id','status'},
        'shared_component_consumers': {'group_id','consumers_json'},
        'staged_conversion_attempts': {'identity','revision','stage','attempt','request_json','response','error'},
        'operation_workflow_progress': {'operation_key','status'},
    }
    columns = {row[1] for row in conn.execute('PRAGMA table_info(' + table + ')')}
    if not (required[table] | {'run_id'}).issubset(columns):
        return []
    try:
        return [dict(row) for row in conn.execute('SELECT rowid AS evidence_rowid,* FROM ' + table + ' WHERE run_id=? ORDER BY rowid', (run_id,))]
    except sqlite3.Error:
        return []


def snapshot(directory, *, include_attempts=True):
    """Read one consistent database view; active writers may continue independently."""
    path = directory / 'state/migration.db'
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        run = conn.execute('SELECT * FROM runs WHERE run_id=?', (directory.name,)).fetchone()
        if run is None:
            raise ValueError('Saved run record not found')
        result = dict(run=dict(run), unavailable_tables=[])
        if not include_attempts:
            return result
        for table in ('behavior_attempts', 'behavior_snapshots', 'conversion_component_plans',
                      'conversion_component_heads', 'shared_component_consumers', 'staged_conversion_attempts',
                      'operation_workflow_progress'):
            result[table] = rows(conn, table, directory.name)
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                result['unavailable_tables'].append(table)
    return result


def journal(directory, limitations):
    """Stream complete JSONL records; interrupted final lines remain explicit limitations."""
    events = []
    for path in sorted(directory.glob('**/reports/model_attempts/events.jsonl')):
        if path.is_symlink() or not path.resolve().is_relative_to(directory):
            continue
        try:
            with path.open(encoding='utf-8') as stream:
                for line in stream:
                    try:
                        event = json.loads(line)
                        if not isinstance(event, dict) or not isinstance(event.get('event'), str):
                            raise ValueError('Invalid event')
                        if any(event.get(key) is not None and not isinstance(event[key], str)
                               for key in ('trace_id', 'identity', 'category', 'fingerprint', 'delivery_id')):
                            raise ValueError('Invalid event identity')
                        event['_folder'] = path.parent.relative_to(directory).as_posix()
                        events.append(event)
                    except ValueError:
                        limitations.add('Some attempt journal records are incomplete or unreadable.')
        except OSError:
            limitations.add('An attempt journal could not be read.')
    return events


def blob_reference(event, name):
    """Resolve only checksum-named captured materials, never arbitrary event paths."""
    identity = event.get(name + '_blob')
    if not isinstance(identity, str) or not re.fullmatch('[0-9a-f]{64}', identity):
        return None
    return dict(storage='blob', path=event['_folder'] + '/blobs/' + identity + '.txt', sha256=identity)


def saved_file_reference(directory, path):
    """Reference an older captured file by its observed bytes without rebuilding it."""
    if path.is_symlink() or not path.resolve().is_relative_to(directory):
        raise ValueError('Captured material leaves the selected run')
    data = path.read_bytes()
    return dict(storage='blob', path=path.relative_to(directory).as_posix(), sha256=hashlib.sha256(data).hexdigest())


def material_text(directory, reference):
    """Retrieve existing captured material with path and checksum verification."""
    if not reference:
        return None
    if reference['storage'] == 'blob':
        path = directory / reference['path']
        if path.is_symlink() or not path.resolve().is_relative_to(directory):
            raise ValueError('Captured material leaves the selected run')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != reference['sha256']:
            raise ValueError('Captured material checksum mismatch')
        return data.decode('utf-8', errors='surrogatepass')
    if reference['storage'] == 'database':
        table, column = reference['table'], reference['column']
        if table not in {'behavior_attempts', 'staged_conversion_attempts'} or column not in {'request_json', 'response', 'error'}:
            raise ValueError('Unsupported saved material')
        with closing(sqlite3.connect((directory / 'state/migration.db').resolve().as_uri() + '?mode=ro', uri=True)) as conn:
            row = conn.execute('SELECT ' + column + ' FROM ' + table + ' WHERE rowid=? AND run_id=?',
                               (reference['rowid'], directory.name)).fetchone()
        if row and column == 'error' and row[0] is not None:
            from runtime.model_execution.error_details import sanitize_diagnostic
            return sanitize_diagnostic(row[0])
        return row[0] if row else None
    raise ValueError('Unknown captured material kind')


def legacy_logs(directory, labels, limitations):
    """Read legacy progress incrementally; attach only explicitly labelled log lines."""
    matched, uncorrelated = [], 0
    for path in sorted((directory / 'logs').glob('**/*.log')):
        if path.is_symlink():
            continue
        try:
            with path.open(encoding='utf-8', errors='replace') as stream:
                for number, line in enumerate(stream, 1):
                    if not re.search(r'Model (?:execution attempt|attempt \d+/\d+ failed|execution completed)', line):
                        continue
                    candidates = [key for label, key in labels.items() if '[' + label + ']' in line]
                    if len(set(candidates)) != 1:
                        uncorrelated += 1
                        continue
                    event = dict(target=candidates[0], file=path.relative_to(directory).as_posix(), line=number)
                    attempt = re.search(r'(?:execution attempt|Model attempt) (\d+)/(\d+)', line)
                    if attempt:
                        event['delivery_attempt'] = int(attempt[1])
                    event['event'] = 'delivery_failed' if ' failed' in line else 'response_received' if ' completed' in line else 'dispatch_attempted'
                    matched.append(event)
        except OSError:
            limitations.add('A legacy log could not be read.')
    if uncorrelated:
        limitations.add(f'{uncorrelated} legacy delivery log lines lack an unambiguous target label; they were not assigned by guesswork.')
    return matched
