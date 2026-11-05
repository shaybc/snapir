"""Rebind current artifact locations after byte-verified moves, retaining original evidence history."""
import json
from pathlib import Path
from tools.conversion_tools.scoped_reuse.fingerprints import digest, revision
from tools.state_store_tools._json import utc_now


def relocate_value(value, movements):
    """Replace complete path prefixes only; source text, logs and historical requests stay intact."""
    if isinstance(value, dict):
        return {relocate_value(k, movements): relocate_value(v, movements) for k, v in value.items()}
    if isinstance(value, list):
        return [relocate_value(v, movements) for v in value]
    if isinstance(value, str):
        for old, new in movements:
            for a, b in [(str(old), str(new)), (Path(old).as_posix(), Path(new).as_posix())]:
                if value == a or value.startswith((a + '/', a + '\\')):
                    return b + value[len(a):]
    return value


def rebind_current_artifacts(conn, run_id, movements):
    """Update only current manifests and scoped bindings after verifying every moved file hash."""
    conn.execute('''CREATE TABLE IF NOT EXISTS artifact_location_migrations (
        run_id TEXT, table_name TEXT, identity TEXT, before_json TEXT, after_json TEXT, migrated_at TEXT)''')
    changed = {}
    def audit(table, identity, before, after):
        conn.execute('INSERT INTO artifact_location_migrations VALUES (?,?,?,?,?,?)',
            (run_id, table, identity, json.dumps(before), json.dumps(after), utc_now()))
        changed[table] = changed.get(table, 0) + 1
    for row in conn.execute('SELECT * FROM behavior_snapshots WHERE run_id=?', (run_id,)).fetchall():
        if row['category'] not in {'manifest', 'project', 'operation'}:
            continue
        old = json.loads(row['data_json']); new = relocate_value(old, movements)
        identity = relocate_value(row['identity'], movements)
        if old != new or identity != row['identity']:
            audit('behavior_snapshots', row['category'] + ':' + row['identity'], dict(identity=row['identity'], data=old), dict(identity=identity, data=new))
            conn.execute('UPDATE behavior_snapshots SET identity=?,data_json=? WHERE run_id=? AND category=? AND identity=?',
                (identity, json.dumps(new), run_id, row['category'], row['identity']))
    for row in conn.execute('SELECT * FROM scoped_reuse_entries WHERE run_id=?', (run_id,)).fetchall():
        before = dict(data=json.loads(row['data_json']), files=json.loads(row['files_json']))
        after = relocate_value(before, movements)
        if before == after:
            continue
        if digest(before) != row['data_hash']:
            raise ValueError('Original scoped artifact integrity is invalid before relocation')
        for path, expected in after['files'].items():
            if revision(path) != expected:
                raise ValueError('Relocated scoped artifact bytes differ: ' + path)
        audit('scoped_reuse_entries', row['identity'], before, after)
        conn.execute('UPDATE scoped_reuse_entries SET data_json=?,files_json=?,data_hash=? WHERE run_id=? AND category=? AND identity=? AND fingerprint=?',
            (json.dumps(after['data']), json.dumps(after['files']), digest(after), run_id, row['category'], row['identity'], row['fingerprint']))
    return changed
