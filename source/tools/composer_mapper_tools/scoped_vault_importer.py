"""Persist scoped source definitions and operation usages without legacy name collisions."""

import hashlib
import json
from pathlib import Path

from tools.composer_mapper_tools.frontmatter_parser import parse_frontmatter
from tools.state_store_tools.channel_operations import upsert_channel_operation, upsert_operation


SCOPED_SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS scoped_vault_runs (
        run_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
        workspace_id TEXT NOT NULL, manifest_hash TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS scoped_source_definitions (
        run_id TEXT NOT NULL, definition_id TEXT NOT NULL, kind TEXT NOT NULL,
        logical_id TEXT NOT NULL, source_hash TEXT NOT NULL, record_json TEXT NOT NULL,
        PRIMARY KEY(run_id, definition_id))''',
    '''CREATE TABLE IF NOT EXISTS scoped_entity_usages (
        run_id TEXT NOT NULL, usage_id TEXT NOT NULL, definition_id TEXT NOT NULL,
        operation_identity TEXT NOT NULL, operation_id TEXT NOT NULL, channel TEXT NOT NULL,
        note_path TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(run_id, usage_id))''',
)


def import_scoped_vault(conn, root, manifest, config, summary):
    """Import complete scoped inventory and graph; never project it into bare-name tables.

    Same-run replacement by different evidence requires a fresh run. Definition sharing
    preserves source provenance and does not imply generated-code reuse or classpath proof.
    """
    from tools.operation_call_tools.discovery import discover_operation_calls
    from tools.state_store_tools.operation_calls import save_graph, plan_contracts
    for statement in SCOPED_SCHEMA:
        conn.execute(statement)
    digest = hashlib.sha256((root / 'vault-manifest.json').read_bytes()).hexdigest()
    previous = conn.execute('SELECT manifest_hash FROM scoped_vault_runs WHERE run_id=?', (config.run_id,)).fetchone()
    if previous is not None and previous[0] != digest:
        raise ValueError('Scoped vault evidence changed; start a fresh run instead of resuming stale identities')
    if conn.execute('SELECT 1 FROM source_artifacts WHERE run_id=? LIMIT 1', (config.run_id,)).fetchone():
        raise ValueError('Cannot replace legacy source identities with scoped identities in the same run')
    parsed = []
    for entry in manifest['entities']:
        text = (root / entry['note']).read_text(encoding='utf-8-sig')
        metadata = parse_frontmatter(text)
        if str(metadata.get('entity_id')) != entry['entity_id'] or metadata.get('qualified_entity_id') != entry['definition_id']:
            raise ValueError('Scoped note and manifest identity disagree: ' + entry['note'])
        parsed.append((entry, metadata))
    with conn:
        conn.execute('INSERT OR REPLACE INTO scoped_vault_runs VALUES (?,?,?,?)',
                     (config.run_id, 2, manifest['workspace_id'], digest))
        for entry, metadata in parsed:
            record = json.dumps(dict(entry, metadata=metadata), sort_keys=True)
            conn.execute('INSERT OR IGNORE INTO scoped_source_definitions VALUES (?,?,?,?,?,?)',
                         (config.run_id, entry['definition_id'], entry['kind'], entry['entity_id'], entry['source_hash'], record))
            conn.execute('INSERT OR REPLACE INTO scoped_entity_usages VALUES (?,?,?,?,?,?,?,?)',
                         (config.run_id, entry['usage_id'], entry['definition_id'], entry.get('operation_identity', ''),
                          entry.get('operation_id', ''), entry.get('channel', ''), str(root / entry['note']), record))
    counts = {'operation': 'operations', 'opStep': 'opsteps', 'format': 'formats', 'context': 'contexts', 'java_class': 'java_classes'}
    seen = set()
    for entry, metadata in parsed:
        identity = entry['definition_id']
        if identity not in seen:
            field = counts.get(entry['kind'])
            if field:
                setattr(summary, field, getattr(summary, field) + 1)
            seen.add(identity)
        if entry['kind'] != 'operation' or not entry.get('operation_id'):
            continue
        channel, operation = entry['channel'], entry['operation_id']
        upsert_channel_operation(conn, operation_name=operation, channel=channel,
                                 xml_file_path=str(metadata.get('source_file', '')), run_id=config.run_id)
        summary.channel_operations += 1
        if config.run_mode.value != 'full_inventory' and channel not in config.target_channels:
            continue
        if config.include_operations and operation not in config.include_operations or operation in (config.exclude_operations or []):
            continue
        upsert_operation(conn, operation_id=operation, channel=channel, run_id=config.run_id,
                         xml_file_path=str(metadata.get('source_file', '')))
    graph = discover_operation_calls(root)
    save_graph(conn, config.run_id, graph)
    plan_contracts(conn, config.run_id, graph, root)
    summary.unresolved_references.extend(issue['operation'] + ': ' + issue['detail'] for issue in graph['issues'])
    return summary


def require_qualified_conversion(conn, run_id):
    """Prevent legacy conversion lookups from selecting arbitrary scoped namesakes."""
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='scoped_vault_runs'").fetchone()
    if exists and conn.execute('SELECT 1 FROM scoped_vault_runs WHERE run_id=?', (run_id,)).fetchone():
        raise ValueError('Scoped vault inventory is supported, but conversion is gated until all closure, reuse, '
                         'and invalidation consumers use qualified identities. Use a collision-free legacy vault '
                         'for existing conversion; never flatten or rename scoped evidence to bypass this gate.')
