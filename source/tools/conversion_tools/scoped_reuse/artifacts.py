"""Reuse only context-bound, fingerprint-matched evidence and validated outputs."""

import json
from pathlib import Path

from tools.conversion_tools.scoped_reuse import state
from tools.conversion_tools.scoped_reuse.fingerprints import digest, revision


def _store_rows(conn, run_id, checkpoint, category, identity, fingerprint, data, files):
    encoded = json.dumps(data, sort_keys=True)
    row = conn.execute('''SELECT data_hash,files_json FROM scoped_reuse_entries
        WHERE run_id=? AND category=? AND identity=? AND fingerprint=?''',
        (run_id, category, identity, fingerprint)).fetchone()
    data_hash = digest(dict(data=data, files=files))
    if row and (row[0] != data_hash or json.loads(row[1]) != files):
        raise ValueError('Qualified artifact identity already has different evidence')
    conn.execute('INSERT OR IGNORE INTO scoped_reuse_entries VALUES (?,?,?,?,?,?,?)',
                 (run_id, category, identity, fingerprint, encoded, data_hash, json.dumps(files, sort_keys=True)))
    conn.execute('INSERT OR REPLACE INTO scoped_reuse_consumers VALUES (?,?,?,?,?,?)',
                 (run_id, checkpoint.operation_identity, category, identity, fingerprint, 'current'))


def _store(conn, *args):
    conn.execute('SAVEPOINT scoped_artifact_binding')
    try:
        _store_rows(conn, *args)
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT scoped_artifact_binding')
        conn.execute('RELEASE SAVEPOINT scoped_artifact_binding')
        raise
    conn.execute('RELEASE SAVEPOINT scoped_artifact_binding')


def load_bound_artifact(conn, run_id, checkpoint, category, identity, fingerprint):
    """Read matching immutable evidence only through a current qualified consumer binding."""
    row = conn.execute('''SELECT e.data_json,e.data_hash,e.files_json FROM scoped_reuse_entries e
        JOIN scoped_reuse_consumers c ON c.run_id=e.run_id AND c.category=e.category
        AND c.identity=e.identity AND c.fingerprint=e.fingerprint
        JOIN scoped_checkpoints p ON p.run_id=c.run_id AND p.operation_identity=c.operation_identity
        WHERE c.run_id=? AND c.operation_identity=? AND c.category=? AND c.identity=? AND c.fingerprint=?
        AND c.status='current' AND p.status='current' AND p.fingerprint=?''',
        (run_id, checkpoint.operation_identity, category, identity, fingerprint, checkpoint.fingerprint)).fetchone()
    if row is None:
        return None
    invalid = False
    try:
        data = json.loads(row[0])
        files = json.loads(row[2])
        invalid = not isinstance(files, dict)
    except (ValueError, TypeError):
        data, files, invalid = None, {}, True
    if invalid or digest(dict(data=data, files=files)) != row[1] or any(revision(path) != value for path, value in files.items()):
        conn.execute('SAVEPOINT scoped_artifact_invalidation')
        try:
            state.invalidate(conn, run_id, checkpoint, ['Saved qualified artifact bytes or metadata changed'])
        except BaseException:
            conn.execute('ROLLBACK TO SAVEPOINT scoped_artifact_invalidation')
            conn.execute('RELEASE SAVEPOINT scoped_artifact_invalidation')
            raise
        conn.execute('RELEASE SAVEPOINT scoped_artifact_invalidation')
        from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale
        raise ScopedCheckpointStale({checkpoint.operation_key: ['Saved qualified artifact bytes or metadata changed']})
    return data


def remember_prepared(conn, run_id, checkpoint, operation, closure):
    """Share only verified source excerpts; units and workflows retain their consuming context."""
    state.save_checkpoint(conn, run_id, checkpoint)
    origins = {origin['definition_id']: origin for origin in closure.java_origins if origin['status'] == 'verified_source'}
    common = checkpoint.inputs['common']
    for unit in operation['units']:
        for source in unit['sources']:
            origin = origins[source['identity']]
            key = digest(dict(definition=source['identity'], revision=source['content_hash'],
                              policy=common['policy'], classpath=common['classpath'], source_root=common['source_root']))
            _store(conn, run_id, checkpoint, 'implementation', source['identity'], key, source,
                   {origin['source_file']: origin['source_hash']})
        _store(conn, run_id, checkpoint, 'configured_unit', unit['unit_id'], unit['fingerprint'], unit, checkpoint.inputs['files'])
    workflow = json.loads(json.dumps(operation))
    for contract in [workflow['contract'], *(workflow[name]['service_contract'] for name in ('behavior_request', 'assembly_request'))]:
        contract.pop('status', None)
    _store(conn, run_id, checkpoint, 'workflow', checkpoint.operation_identity, checkpoint.fingerprint,
           workflow, checkpoint.inputs['files'])


def reuse_prepared(conn, run_id, records, selected):
    """Return a complete selected preparation only when every context has verified cache proof."""
    by_key = {record.operation_key: record for record in records.values() if record.status == 'current'}
    operations = {}
    for key in sorted(selected):
        checkpoint = by_key.get(key)
        if checkpoint is None:
            return None
        item = load_bound_artifact(conn, run_id, checkpoint, 'workflow', checkpoint.operation_identity, checkpoint.fingerprint)
        if item is None:
            return None
        from tools.state_store_tools.operation_calls import get_contract
        item['contract'] = get_contract(conn, run_id, key)
        for name in ('behavior_request', 'assembly_request'):
            item[name]['service_contract'] = dict(item['contract'])
        operations[key] = item
    return operations


def save_validated_output(conn, config, profile, classpath, operation_key, unit_id, category, identity,
                          data, files, *, validator):
    """Bind an existing validator's successful result to exact scoped proof, without generating code.

    This adapter does not mark compilation/review/gates passed; the required validator
    owns acceptance. C6 must integrate native generation before enabling that path.
    """
    if category not in ('task', 'result', 'native_artifact'):
        raise ValueError('Unsupported scoped output category')
    from tools.conversion_tools.scoped_reuse.checkpoint import validate_checkpoints
    validate_checkpoints(conn, config, profile, classpath, {operation_key})
    record = next((item for item in state.checkpoints(conn, config.run_id).values() if item.operation_key == operation_key), None)
    if record is None or unit_id not in record.units:
        raise ValueError('Configured unit is not bound to this consuming context')
    root = Path(config.output_root).resolve()
    manifest = {}
    for filename in files:
        path = Path(filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Native output file must exist within this run output root')
        value = revision(path)
        if value is None:
            raise ValueError('Native output file disappeared during fingerprinting')
        manifest[str(path)] = value
    if category == 'native_artifact' and not manifest:
        raise ValueError('Native artifact requires an output file manifest')
    if validator(data) is False:
        raise ValueError('Scoped output validator rejected the result')
    # Recheck after validation, which may run a compiler or inspect external files.
    validate_checkpoints(conn, config, profile, classpath, {operation_key})
    if any(revision(path) != value for path, value in manifest.items()):
        raise ValueError('Native output changed during validation')
    key = digest(dict(context=record.operation_identity, unit=unit_id, category=category, identity=identity))
    fingerprint = digest(dict(checkpoint=record.fingerprint, unit=record.units[unit_id], identity=identity))
    _store(conn, config.run_id, record, category, key, fingerprint, data, manifest)
    return key, fingerprint


def reuse_validated_output(conn, config, profile, classpath, operation_key, unit_id, category, identity, *, validator):
    """Revalidate saved output; exact identity never falls back to legacy compatibility."""
    from tools.conversion_tools.scoped_reuse.checkpoint import validate_checkpoints
    validate_checkpoints(conn, config, profile, classpath, {operation_key})
    record = next((item for item in state.checkpoints(conn, config.run_id).values() if item.operation_key == operation_key), None)
    if record is None or unit_id not in record.units:
        return None
    key = digest(dict(context=record.operation_identity, unit=unit_id, category=category, identity=identity))
    fingerprint = digest(dict(checkpoint=record.fingerprint, unit=record.units[unit_id], identity=identity))
    data = load_bound_artifact(conn, config.run_id, record, category, key, fingerprint)
    if data is not None:
        if validator(data) is False:
            raise ValueError('Scoped output validator rejected cached evidence')
        validate_checkpoints(conn, config, profile, classpath, {operation_key})
        data = load_bound_artifact(conn, config.run_id, record, category, key, fingerprint)
    return data
