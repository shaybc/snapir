"""Persist sanitized connection evidence and resource-scoped user decisions."""

import json


def initialize(conn):
    """Add connection tables without changing existing migration schema or artifacts."""
    conn.execute('''CREATE TABLE IF NOT EXISTS service_connection_evidence (
        run_id TEXT, consumer TEXT, unit_key TEXT, connection_id TEXT, fingerprint TEXT,
        record_json TEXT, PRIMARY KEY(run_id,consumer,unit_key,connection_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS service_connection_decisions (
        run_id TEXT, connection_id TEXT, fingerprint TEXT, answer_json TEXT,
        PRIMARY KEY(run_id,connection_id,fingerprint))''')


def remember(conn, run_id, consumer, unit_key, records):
    """Store only this consumer's currently relevant resolved records."""
    initialize(conn)
    with conn:
        conn.execute('DELETE FROM service_connection_evidence WHERE run_id=? AND consumer=? AND unit_key=?',
                     (run_id, consumer, unit_key))
        for item in records:
            conn.execute('INSERT INTO service_connection_evidence VALUES (?,?,?,?,?,?)',
                (run_id, consumer, unit_key, item.connection_id, item.fingerprint, item.model_dump_json()))


def decision(conn, run_id, identity, fingerprint):
    """Reuse an answer only when the same resource evidence still applies."""
    initialize(conn)
    row = conn.execute('SELECT answer_json FROM service_connection_decisions WHERE run_id=? AND connection_id=? AND fingerprint=?',
                       (run_id, identity, fingerprint)).fetchone()
    return json.loads(row[0]) if row else None


def save_decision(conn, run_id, identity, fingerprint, answer):
    """Persist a validated resource-scoped decision; retain prior evidence versions."""
    initialize(conn)
    allowed = {'driver_dependency', 'service_alias', 'transaction_scope'}
    if not isinstance(answer, dict) or not answer or set(answer) - allowed:
        raise ValueError('Connection answer must contain driver_dependency, service_alias or transaction_scope')
    if 'driver_dependency' in answer:
        from models.maven_dependency import MavenDependency
        value = MavenDependency.model_validate(answer['driver_dependency'])
        if value.scope not in {'runtime', 'compile'}:
            raise ValueError('A production driver must have compile or runtime scope')
    if 'transaction_scope' in answer and answer['transaction_scope'] not in {'step', 'operation', 'caller'}:
        raise ValueError('Transaction scope must be step, operation or caller')
    if 'service_alias' in answer:
        import re
        if not isinstance(answer['service_alias'], str) or not re.fullmatch(r'[\w.:-]+', answer['service_alias']):
            raise ValueError('A service alias must name a configured service instance')
    with conn:
        conn.execute('INSERT OR REPLACE INTO service_connection_decisions VALUES (?,?,?,?)',
                     (run_id, identity, fingerprint, json.dumps(answer)))


def pending_questions(conn, run_id):
    """Group unresolved resource facts and list all their affected unit consumers."""
    initialize(conn)
    questions = {}
    for row in conn.execute('SELECT consumer,unit_key,record_json FROM service_connection_evidence WHERE run_id=?', (run_id,)):
        data = json.loads(row[2])
        if not data['issues']:
            continue
        key = (data.get('decision_id') or data['connection_id'], data.get('decision_fingerprint') or data['fingerprint'])
        item = questions.setdefault(key, dict(connection_id=key[0], fingerprint=key[1], channel=data['channel'],
            service_id=data['service_id'], connector_id=data['connector_id'], issues=data['issues'],
            driver_class=data['driver_class'], driver_candidates=data['driver_candidates'], consumers=[]))
        item['issues'] = sorted(set(item['issues'] + data['issues']))
        item['consumers'].append(row[0] + ' / ' + row[1])
    return list(questions.values())
