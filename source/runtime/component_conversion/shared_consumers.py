"""Reuse existing global inventory counts for neutral-class library placement."""
from pathlib import Path


def original_consumers(conn, run_id, plan, source_root=None):
    """Count class uses outside selected operations without treating configured variants as classes."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='source_implementations'").fetchone():
        return {}
    selected = {}
    for key, node in plan.components.items():
        if node.kind != 'java_implementation':
            continue
        origin = node.provenance
        path = ''
        if source_root and origin.get('source_file'):
            try:
                path = Path(origin['source_file']).resolve().relative_to(Path(source_root).resolve()).as_posix()
            except ValueError:
                continue
        selected.setdefault((node.label, origin.get('source_hash'), path), []).append(key)
    if not selected:
        return {}
    conn.execute('CREATE TEMP TABLE IF NOT EXISTS shared_source_candidates (fqcn TEXT, source_hash TEXT, source_path TEXT)')
    conn.execute('DELETE FROM shared_source_candidates')
    conn.executemany('INSERT INTO shared_source_candidates VALUES (?,?,?)', selected)
    query = '''SELECT i.implementation_id,s.fqcn,s.source_hash,s.source_path FROM source_implementations i
        JOIN shared_source_candidates s ON s.source_hash=i.source_hash
        AND s.fqcn=CASE WHEN json_extract(i.record_json,'$.package_name')='' THEN json_extract(i.record_json,'$.class_name')
            ELSE json_extract(i.record_json,'$.package_name')||'.'||json_extract(i.record_json,'$.class_name') END
        AND (s.source_path='' OR s.source_path=json_extract(i.record_json,'$.source_path')) WHERE i.run_id=?'''
    from tools.state_store_tools.java_usage import consumer_query, direct_consumer_query
    inherited = consumer_query(conn, run_id)
    direct = direct_consumer_query(conn, run_id)
    result = {}
    for implementation, name, source_hash, path in conn.execute(query, (run_id,)).fetchall():
        consumers = set()
        for statement in (inherited, direct):
            consumers.update((row[2] or '') + '/' + row[1] for row in conn.execute(statement, (run_id, implementation)))
        for key in selected[(name, source_hash, path)]:
            result.setdefault(key, set()).update(consumers)
    return result
