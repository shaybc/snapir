"""Query exact global consumers from compact factors, with compatibility for older detailed runs."""

import json
from models.java_usage_summary import JavaUsageSummary


def factorized_usage(conn, run_id):
    """Detect an explicitly scoped summary; an empty selected scope remains distinguishable."""
    row = conn.execute('SELECT graph_json FROM java_dependency_reports WHERE run_id=?', (run_id,)).fetchone()
    return bool(row and json.loads(row[0]).get('usage_storage') == 'factors-v1')


def iter_global_java_usage(conn, run_id, *, implementation_id=None, candidates=False):
    """Yield exact counts, multiplying integer factors in Python to avoid SQLite overflow."""
    if factorized_usage(conn, run_id):
        query = '''SELECT t.target,r.operation_key,r.operation_id,r.channel,t.count,r.weight FROM java_usage_targets t
            JOIN java_usage_roots r ON r.run_id=t.run_id AND r.root=t.root WHERE t.run_id=?'''
        parameters = (run_id,)
        if implementation_id is not None:
            query += ' AND t.target=?'
            parameters += (implementation_id,)
        if candidates:
            query += " AND 'implementation:'||t.target IN (SELECT component_key FROM library_plan_candidates)"
        for target, key, name, channel, count, weight in conn.execute(query, parameters):
            yield JavaUsageSummary(implementation_id=target, operation_key=key, operation_id=name, channel=channel,
                                   reference_count=int(count) * int(weight))
    else:
        query, parameters = 'SELECT record_json FROM java_dependency_uses WHERE run_id=?', (run_id,)
        if implementation_id is not None:
            query += ' AND implementation_id=?'
            parameters += (implementation_id,)
        if candidates:
            query += " AND 'implementation:'||implementation_id IN (SELECT component_key FROM library_plan_candidates)"
        for (record,) in conn.execute(query, parameters):
            value = json.loads(record)
            value.setdefault('reference_count', 1)
            yield JavaUsageSummary.model_validate(value)


def consumer_query(conn, run_id):
    """Return a parameterized exact consumer relation for one implementation."""
    if factorized_usage(conn, run_id):
        return '''SELECT r.operation_key,r.operation_id,r.channel FROM java_usage_targets t JOIN java_usage_roots r
            ON r.run_id=t.run_id AND r.root=t.root WHERE t.run_id=? AND t.target=?'''
    return 'SELECT operation_key,operation_id,channel FROM java_dependency_uses WHERE run_id=? AND implementation_id=?'


def check_detailed_scope(conn, run_id, consumers):
    """Reject attempts to plan outside a segmented snapshot instead of silently omitting dependencies."""
    if not factorized_usage(conn, run_id):
        return
    for consumer in consumers:
        if not conn.execute('SELECT 1 FROM java_usage_operations WHERE run_id=? AND consumer=?', (run_id, consumer)).fetchone():
            raise ValueError('Operation is outside this run\'s detailed inventory scope: ' + consumer + '; start a new run with this operation selected')
