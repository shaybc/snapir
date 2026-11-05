"""Read normalized dependency rows with selected-root reachability and old-run fallback."""

import json


def graph_storage(conn, run_id):
    """Identify row-based graphs without confusing older empty graphs with new storage."""
    row = conn.execute('SELECT graph_json FROM java_dependency_reports WHERE run_id=?', (run_id,)).fetchone()
    metadata = json.loads(row[0]) if row else {}
    return metadata, metadata.get('storage') == 'rows-v1'


def reachable_ids(conn, run_id, roots):
    """Return only reachable implementation identities using a disk-backed recursive queue."""
    conn.execute('CREATE TEMP TABLE IF NOT EXISTS graph_roots (identity TEXT PRIMARY KEY)')
    conn.execute('DELETE FROM graph_roots')
    conn.executemany('INSERT OR IGNORE INTO graph_roots VALUES (?)', ((root,) for root in roots))
    return {row[0] for row in conn.execute('''WITH RECURSIVE reach(identity) AS (
        SELECT identity FROM graph_roots UNION SELECT e.target FROM java_dependency_edges e
        JOIN reach r ON e.caller=r.identity WHERE e.run_id=?) SELECT identity FROM reach''', (run_id,))}


def graph_rows(conn, run_id, *, roots=None):
    """Load the selected subgraph; whole-graph compatibility callers can omit roots."""
    from models.java_source_dependencies import JavaSourceDependencyGraph, JavaSourceDependency, JavaDependencyIssue
    metadata, normalized = graph_storage(conn, run_id)
    if not normalized:
        return JavaSourceDependencyGraph.model_validate(metadata)
    graph = JavaSourceDependencyGraph(analysis_scope=metadata['analysis_scope'])
    selected = reachable_ids(conn, run_id, roots) if roots is not None else None
    # Selection uses a temporary table to avoid SQLite bind-variable limits.
    conn.execute('CREATE TEMP TABLE IF NOT EXISTS graph_selected (identity TEXT PRIMARY KEY)')
    if selected is not None:
        conn.execute('DELETE FROM graph_selected')
        conn.executemany('INSERT INTO graph_selected VALUES (?)', ((value,) for value in selected))
    clause = ' AND caller IN (SELECT identity FROM graph_selected)' if selected is not None else ''
    graph.dependencies = [JavaSourceDependency.model_validate_json(row[0]) for row in conn.execute(
        'SELECT record_json FROM java_dependency_edges WHERE run_id=?' + clause + ' ORDER BY dependency_id', (run_id,))]
    clause = ' AND implementation_id IN (SELECT identity FROM graph_selected)' if selected is not None else ''
    graph.issues = [JavaDependencyIssue.model_validate_json(row[0]) for row in conn.execute(
        'SELECT record_json FROM java_dependency_issues WHERE run_id=?' + clause + ' ORDER BY issue_id', (run_id,))]
    return graph
