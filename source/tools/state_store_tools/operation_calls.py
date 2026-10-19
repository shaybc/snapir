"""Persist mapped operation calls and versioned native HTTP contracts."""

import hashlib
import json
from pathlib import Path
from urllib.parse import quote


def initialize(conn):
    """Add operation-call state without changing existing tables."""
    conn.execute('CREATE TABLE IF NOT EXISTS operation_call_graphs (run_id TEXT PRIMARY KEY, graph_json TEXT NOT NULL)')
    conn.execute('''CREATE TABLE IF NOT EXISTS operation_service_contracts (
        run_id TEXT NOT NULL, operation_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
        status TEXT NOT NULL, contract_json TEXT NOT NULL, PRIMARY KEY(run_id, operation_key))''')


def save_graph(conn, run_id, graph):
    """Replace mapped evidence atomically; callers own the transaction."""
    initialize(conn)
    conn.execute('INSERT OR REPLACE INTO operation_call_graphs VALUES (?,?)', (run_id, json.dumps(graph, sort_keys=True)))


def load_graph(conn, run_id):
    """Read the graph or return None for runs created before call discovery."""
    initialize(conn)
    row = conn.execute('SELECT graph_json FROM operation_call_graphs WHERE run_id=?', (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def plan_contracts(conn, run_id, graph, vault):
    """Define stable XML HTTP contracts from mapped formats, retaining validation only for identical facts."""
    initialize(conn)
    root = Path(vault)
    from tools.composer_mapper_tools.frontmatter_parser import parse_frontmatter
    format_notes = {}
    for path in (root / 'formats').rglob('*.md'):
        text = path.read_text(encoding='utf-8-sig')
        format_notes.setdefault(parse_frontmatter(text).get('entity_id'), []).append(text)
    for key, operation in graph['operations'].items():
        formats = {}
        for role, name in operation['ref_formats'].items():
            # Mapper encodes unsafe filename characters; resolve by entity identity.
            matches = format_notes.get(name, [])
            formats[role] = dict(name=name, markdown=matches[0]) if len(matches) == 1 else dict(name=name, unresolved=True)
        contract = dict(operation=key, method='POST', path='/operations/' + '/'.join(quote(part, safe='') for part in key.split('/')),
            media_type='application/xml', base_url_property='operations.' + hashlib.sha256(key.encode()).hexdigest()[:12] + '.base-url',
            formats=formats, source_hash=operation['source_hash'],
            call_evidence=[call for call in graph['calls'] if call['caller'] == key],
            error_policy='Preserve target error XML and map evidenced return outcomes; report unknown mappings.')
        digest = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
        prior = conn.execute('SELECT fingerprint,status FROM operation_service_contracts WHERE run_id=? AND operation_key=?', (run_id, key)).fetchone()
        status = prior[1] if prior and prior[0] == digest else 'planned'
        conn.execute('INSERT OR REPLACE INTO operation_service_contracts VALUES (?,?,?,?,?)',
                     (run_id, key, digest, status, json.dumps(contract, sort_keys=True)))


def get_contract(conn, run_id, key):
    """Return explicit contract state without implying a deployed service."""
    initialize(conn)
    row = conn.execute('SELECT fingerprint,status,contract_json FROM operation_service_contracts WHERE run_id=? AND operation_key=?', (run_id, key)).fetchone()
    if row is None:
        raise ValueError('Native operation contract is unavailable: ' + key)
    return dict(json.loads(row[2]), fingerprint=row[0], status=row[1])


def set_contract_status(conn, run_id, key, status):
    """Record assembly or service validation, separately from runtime deployment."""
    if status not in {'planned', 'assembled', 'validated'}:
        raise ValueError('Unknown operation contract status: ' + status)
    conn.execute('UPDATE operation_service_contracts SET status=? WHERE run_id=? AND operation_key=?', (status, run_id, key))
