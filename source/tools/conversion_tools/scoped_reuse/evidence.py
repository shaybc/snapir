"""Capture source layout and exact consuming-context inputs for freshness checks."""

import json
import re
from pathlib import Path

from tools.composer_mapper_tools.frontmatter_parser import parse_section
from tools.component_inventory_tools.channel_mappings import channel_for_path
from tools.conversion_tools.scoped_reuse.fingerprints import digest, revision


def source_layout(source_root):
    """Snapshot registry bytes, XML membership, and Java project metadata at intake."""
    root = Path(source_root).resolve() if source_root else None
    if root is None or not root.is_dir():
        return dict(status='unavailable')
    registries, documents, projects = {}, {}, {}
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(root):
            continue
        relative = path.relative_to(root).as_posix()
        channel = channel_for_path(path) or ''
        if path.name.lower() in ('dse.ini', 'dsc.ini'):
            registries.setdefault(channel, {})[relative] = revision(path)
        elif path.name in ('.classpath', '.project'):
            projects[relative] = revision(path)
        elif path.suffix.lower() == '.xml':
            documents.setdefault(channel, []).append(relative)
    return dict(status='captured', source_root=str(root), registries=registries, documents=documents, projects=projects)


def channel_layout(layout, channel, markdown):
    """Restrict channel registry/definition membership evidence to its import chain."""
    chain = parse_section(markdown, 'Import Chain')
    channels = {channel.upper(), 'XML', ''}
    for name in layout.get('registries', {}):
        if name and re.search(r'(?<![\w])' + re.escape(name) + r'(?![\w])', chain, re.IGNORECASE):
            channels.add(name)
    return dict(status=layout['status'], source_root=layout.get('source_root'), projects=layout.get('projects', {}),
        registries={name: layout.get('registries', {}).get(name, {}) for name in sorted(channels)},
        documents={name: layout.get('documents', {}).get(name, []) for name in sorted(channels)})


def context_facts(conn, run_id, identity):
    """Read actual imported bindings as well as their declarative manifest record."""
    row = conn.execute('''SELECT channel,operation_id,selected,record_json FROM scoped_operation_contexts
        WHERE run_id=? AND operation_identity=?''', (run_id, identity)).fetchone()
    if row is None:
        return None
    bindings = [tuple(item) for item in conn.execute('''SELECT binding_kind,binding_key,definition_id,note_path
        FROM scoped_context_bindings WHERE run_id=? AND operation_identity=? ORDER BY binding_kind,binding_key''',
        (run_id, identity))]
    definitions = [tuple(item) for item in conn.execute('''SELECT DISTINCT d.definition_id,d.record_json
        FROM scoped_source_definitions d JOIN scoped_context_bindings b
        ON b.run_id=d.run_id AND b.definition_id=d.definition_id
        WHERE b.run_id=? AND b.operation_identity=? ORDER BY d.definition_id''', (run_id, identity))]
    usages = [tuple(item) for item in conn.execute('''SELECT DISTINCT u.note_path,u.record_json
        FROM scoped_entity_usages u JOIN scoped_context_bindings b
        ON b.run_id=u.run_id AND b.definition_id=u.definition_id AND b.note_path=u.note_path
        WHERE b.run_id=? AND b.operation_identity=? ORDER BY u.note_path,u.record_json''', (run_id, identity))]
    channel = conn.execute('SELECT record_json FROM scoped_channel_evidence WHERE run_id=? AND channel=?',
                           (run_id, row[0])).fetchone()
    return dict(channel=row[0], operation_id=row[1], selected=row[2], context=json.loads(row[3]), bindings=bindings,
                definitions=definitions,
                usages=usages,
                channel_evidence=json.loads(channel[0]) if channel else None)


def input_files(closure, root):
    """Retain file-level revisions of actual XML/Java/binary consumers."""
    files = {str((Path(root) / path).resolve()): value for path, value in closure.source_revisions.items()}
    for origin in closure.java_origins:
        if origin['status'] == 'verified_source':
            files[str(Path(origin['source_file']).resolve())] = origin['source_hash']
        elif origin['status'] in ('verified_retention', 'verified_platform'):
            files[str(Path(origin['location'][4:]).resolve())] = origin['source_hash']
    return files


def call_bindings(conn, run_id, operation_key):
    """Fingerprint only pins/decisions relevant to this caller, not unrelated services."""
    row = conn.execute('''SELECT record_json FROM scoped_operation_contexts
        WHERE run_id=? AND channel=? AND operation_id=?''', (run_id, *operation_key.split('/', 1))).fetchone()
    targets = {item.get('target_context') for item in json.loads(row[0])['calls']} if row else set()
    from tools.state_store_tools.service_api_uses import list_service_uses
    pins = [use.model_dump(mode='json') for use in list_service_uses(conn, run_id)
            if use.contract.channel + '/' + use.contract.operation_id in targets]
    pinned_targets = {item['contract']['channel'] + '/' + item['contract']['operation_id'] for item in pins}
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE name='operation_service_contracts'").fetchone()
    contracts = [tuple(row) for row in conn.execute('''SELECT operation_key,fingerprint,contract_json
        FROM operation_service_contracts WHERE run_id=? ORDER BY operation_key''', (run_id,))
        if row[0] in targets - pinned_targets or row[0] == operation_key] if table else []
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE name='service_connection_decisions'").fetchone()
    decisions = [tuple(row) for row in conn.execute('''SELECT connection_id,fingerprint,answer_json
        FROM service_connection_decisions WHERE run_id=? ORDER BY connection_id,fingerprint''', (run_id,))] if table else []
    # Connection decisions are conservative until their resource graph proves a smaller scope.
    return digest(dict(pins=pins, contracts=contracts, connection_decisions=decisions))
