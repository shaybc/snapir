"""Import canonical schema-three evidence and contextual bindings atomically, without conversion."""

import hashlib
import json
import time
from datetime import datetime

from tools.composer_mapper_tools.frontmatter_parser import parse_frontmatter
from tools.composer_mapper_tools.scoped_context_state import SCOPED_CONTEXT_SCHEMA
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest, intake_evidence
from tools.composer_mapper_tools.scoped_vault_importer import SCOPED_SCHEMA
from tools.state_store_tools._json import utc_now


def _parsed_note(entry, text, path):
    """Reuse note parsers while retaining complete Markdown for future qualified resolvers."""
    from tools.composer_mapper_tools.operation_parser import parse_operation_note
    from tools.composer_mapper_tools.opstep_parser import parse_opstep_note
    from tools.composer_mapper_tools.format_parser import parse_format_note
    from tools.composer_mapper_tools.context_parser import parse_context_note
    from tools.composer_mapper_tools.java_class_parser import parse_java_class_note
    parser = {'operation': parse_operation_note, 'opStep': parse_opstep_note,
              'format': parse_format_note, 'context': parse_context_note,
              'java_class': parse_java_class_note}.get(entry['kind'])
    return parser(text, str(path)).model_dump(mode='json') if parser else {}


def import_shared_vault(conn, root, manifest, config, summary, *, progress=None, validated_hash=None):
    """Publish inventory-ready state only after the complete import succeeds.

    The caller supplies a validated manifest. A savepoint rolls back all imported
    records on failure; the scoped conversion guard deliberately remains active.
    """
    root = root.resolve()
    started, last = time.monotonic(), 0.0

    def report(message, force=False):
        nonlocal last
        now = time.monotonic()
        if force or now - last >= 5:
            (progress or print)(f'[{datetime.now().astimezone().isoformat(timespec="seconds")}] '
                                f'{message} | elapsed={now - started:.1f}s')
            last = now

    report('Starting schema-three inventory import; conversion remains gated', True)
    conn.execute('SAVEPOINT shared_vault_intake')
    try:
        for statement in (*SCOPED_SCHEMA, *SCOPED_CONTEXT_SCHEMA):
            conn.execute(statement)
        digest = file_digest(root / 'vault-manifest.json')
        if validated_hash != digest:
            raise ValueError('Scoped manifest changed after validation')
        evidence = intake_evidence(root, manifest, config)
        snapshot = json.dumps(evidence, sort_keys=True)
        evidence_hash = hashlib.sha256(snapshot.encode('utf-8')).hexdigest()
        previous = conn.execute('SELECT manifest_hash FROM scoped_vault_runs WHERE run_id=?', (config.run_id,)).fetchone()
        previous_evidence = conn.execute('SELECT evidence_hash FROM scoped_intake_evidence WHERE run_id=?', (config.run_id,)).fetchone()
        if previous and (previous[0] != digest or not previous_evidence or previous_evidence[0] != evidence_hash):
            raise ValueError('Scoped evidence or intake settings changed; start a fresh run')
        if conn.execute('SELECT 1 FROM source_artifacts WHERE run_id=? LIMIT 1', (config.run_id,)).fetchone():
            raise ValueError('Cannot replace legacy source identities with scoped identities in the same run')
        contexts = manifest['operation_contexts']
        available = {context['channel'] for context in contexts}
        if available - set(manifest.get('channels', [])):
            raise ValueError('Execution context channel is missing from declared channel evidence')
        if config.run_mode.value != 'full_inventory' and set(config.target_channels) - available:
            raise ValueError('Missing consuming-channel operation execution evidence')
        selected_channels = available if config.run_mode.value == 'full_inventory' else set(config.target_channels)
        for name in config.include_operations or []:
            if not any(c['operation_id'] == name and c['channel'] in selected_channels for c in contexts):
                raise ValueError('Missing requested operation execution context: ' + name)
        by_note = {entry['note']: entry for entry in manifest['entities']}
        counts = {'operation': 'operations', 'opStep': 'opsteps', 'format': 'formats',
                  'context': 'contexts', 'java_class': 'java_classes'}
        counted = set()
        for ordinal, entry in enumerate(manifest['entities'], 1):
            path = root / entry['note']
            # Verify again at the import boundary: notes may change after validation.
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry['note_hash']:
                raise ValueError('Scoped note changed during import: ' + entry['note'])
            text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
            record = json.dumps(dict(entry, metadata=parse_frontmatter(text),
                                     parsed=_parsed_note(entry, text, path), markdown=text), sort_keys=True)
            conn.execute('INSERT OR IGNORE INTO scoped_source_definitions VALUES (?,?,?,?,?,?)',
                         (config.run_id, entry['definition_id'], entry['kind'], entry['entity_id'], entry['source_hash'], record))
            if entry['definition_id'] not in counted and entry['kind'] in counts:
                field = counts[entry['kind']]
                setattr(summary, field, getattr(summary, field) + 1)
            counted.add(entry['definition_id'])
            conn.execute('INSERT OR REPLACE INTO scoped_entity_usages VALUES (?,?,?,?,?,?,?,?)',
                         (config.run_id, entry['usage_id'], entry['definition_id'], entry.get('operation_identity', ''),
                          entry.get('operation_id', ''), entry.get('channel', ''), str(path), record))
            report(f'Importing note {ordinal}/{len(by_note)}: {entry["note"]}')
        identities = set()
        for context in contexts:
            identity = context['operation_identity']
            if identity in identities:
                raise ValueError('Duplicate execution context identity: ' + identity)
            identities.add(identity)
            selected = context['channel'] in selected_channels and (
                not config.include_operations or context['operation_id'] in config.include_operations
            ) and context['operation_id'] not in (config.exclude_operations or [])
            conn.execute('INSERT OR REPLACE INTO scoped_operation_contexts VALUES (?,?,?,?,?,?,?,?)',
                         (config.run_id, identity, context['channel'], context['operation_id'],
                          context['definition_id'], str(root / context['note']), int(selected), json.dumps(context, sort_keys=True)))
            for kind, bindings in (('reference', context['references'].items()),
                                   ('step', ((str(i), note) for i, note in enumerate(context['step_notes'])))):
                for key, note in bindings:
                    conn.execute('INSERT OR REPLACE INTO scoped_context_bindings VALUES (?,?,?,?,?,?)',
                                 (config.run_id, identity, kind, key, by_note[note]['definition_id'], str(root / note)))
            source = by_note[context['note']]['source_relative_path']
            conn.execute('''INSERT INTO channel_operations VALUES (?,?,?,?)
                            ON CONFLICT(operation_name,channel,run_id) DO NOTHING''',
                         (context['operation_id'], context['channel'], source, config.run_id))
            summary.channel_operations += 1
            if selected:
                now = utc_now()
                conn.execute('''INSERT INTO operations
                    (operation_id,channel,run_id,xml_file_path,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?) ON CONFLICT(operation_id,channel,run_id) DO NOTHING''',
                    (context['operation_id'], context['channel'], config.run_id, source, 'pending', now, now))
        for channel, channel_evidence in evidence['channels'].items():
            conn.execute('INSERT OR REPLACE INTO scoped_channel_evidence VALUES (?,?,?,?,?)',
                         (config.run_id, channel, channel_evidence['note'], channel_evidence['note_hash'],
                          json.dumps(channel_evidence, sort_keys=True)))
        if file_digest(root / 'vault-manifest.json') != digest or (root / 'vault-generation.json').exists():
            raise ValueError('Scoped manifest changed during import')
        if intake_evidence(root, manifest, config) != evidence:
            raise ValueError('Channel or configuration evidence changed during import')
        conn.execute('INSERT OR REPLACE INTO scoped_intake_evidence VALUES (?,?,?,?)',
                     (config.run_id, manifest['identity_version'], evidence_hash, snapshot))
        conn.execute('INSERT OR REPLACE INTO scoped_vault_runs VALUES (?,?,?,?)',
                     (config.run_id, manifest['vault_schema_version'], manifest['workspace_id'], digest))
        conn.execute('RELEASE SAVEPOINT shared_vault_intake')
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT shared_vault_intake')
        conn.execute('RELEASE SAVEPOINT shared_vault_intake')
        report('FAILED schema-three inventory import; no ready import published', True)
        raise
    summary.unresolved_references.extend(str(item.get('detail', item)) for item in manifest.get('diagnostics', []))
    report(f'Inventory ready: {len(by_note)} notes, {len(contexts)} execution contexts; conversion remains gated', True)
    return summary
