"""Persist authoritative implementation identities and configured-use evidence per run."""

import json


INVENTORY_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS java_direct_usage (run_id TEXT,target TEXT,operation_key TEXT,operation_id TEXT,channel TEXT,weight TEXT)",
    "CREATE INDEX IF NOT EXISTS direct_usage_targets ON java_direct_usage(run_id,target)",
    "CREATE TABLE IF NOT EXISTS configured_global_usage (run_id TEXT,definition TEXT,operation_key TEXT,operation_id TEXT,channel TEXT,weight TEXT)",
    "CREATE INDEX IF NOT EXISTS configured_global_ids ON configured_global_usage(run_id,definition)",
    "CREATE TABLE IF NOT EXISTS java_usage_roots (run_id TEXT,root TEXT,operation_key TEXT,operation_id TEXT,channel TEXT,weight TEXT)",
    "CREATE INDEX IF NOT EXISTS java_usage_root_ids ON java_usage_roots(run_id,root)",
    "CREATE TABLE IF NOT EXISTS java_usage_targets (run_id TEXT,root TEXT,target TEXT,count TEXT,PRIMARY KEY(run_id,root,target))",
    "CREATE INDEX IF NOT EXISTS java_usage_target_ids ON java_usage_targets(run_id,target)",
    "CREATE TABLE IF NOT EXISTS java_usage_scope (run_id TEXT,target TEXT,PRIMARY KEY(run_id,target))",
    "CREATE TABLE IF NOT EXISTS java_usage_operations (run_id TEXT,consumer TEXT,PRIMARY KEY(run_id,consumer))",
    """CREATE TABLE IF NOT EXISTS java_dependency_edges (run_id TEXT, dependency_id TEXT,
        caller TEXT, target TEXT, record_json TEXT, PRIMARY KEY(run_id,dependency_id))""",
    "CREATE INDEX IF NOT EXISTS java_edge_callers ON java_dependency_edges(run_id,caller)",
    """CREATE TABLE IF NOT EXISTS java_dependency_issues (run_id TEXT, issue_id TEXT,
        implementation_id TEXT, record_json TEXT, PRIMARY KEY(run_id,issue_id))""",
    """CREATE TABLE IF NOT EXISTS source_implementations (
        run_id TEXT NOT NULL, implementation_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
        source_hash TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(run_id,implementation_id))""",
    """CREATE TABLE IF NOT EXISTS configured_component_uses (
        run_id TEXT NOT NULL, use_id TEXT NOT NULL, implementation_id TEXT,
        operation_key TEXT NOT NULL, operation_id TEXT NOT NULL, channel TEXT,
        component_kind TEXT NOT NULL, configuration_hash TEXT NOT NULL, record_json TEXT NOT NULL,
        PRIMARY KEY(run_id,use_id), FOREIGN KEY(run_id,implementation_id)
        REFERENCES source_implementations(run_id,implementation_id))""",
    """CREATE TABLE IF NOT EXISTS component_inventory_reports (
        run_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, diagnostics_json TEXT NOT NULL,
        analysis_scope TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS configured_component_definitions (
        run_id TEXT NOT NULL, definition_id TEXT NOT NULL, implementation_id TEXT,
        component_kind TEXT NOT NULL, configuration_hash TEXT NOT NULL, record_json TEXT NOT NULL,
        PRIMARY KEY(run_id,definition_id))""",
    """CREATE TABLE IF NOT EXISTS java_dependency_reports (
        run_id TEXT PRIMARY KEY, graph_json TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS java_dependency_uses (
        run_id TEXT NOT NULL, use_id TEXT NOT NULL, implementation_id TEXT NOT NULL,
        operation_key TEXT NOT NULL, operation_id TEXT NOT NULL, channel TEXT,
        record_json TEXT NOT NULL, PRIMARY KEY(run_id,use_id))""",
    "CREATE INDEX IF NOT EXISTS java_use_implementations ON java_dependency_uses(run_id,implementation_id)",
    "CREATE INDEX IF NOT EXISTS configured_use_operations ON configured_component_uses(run_id,channel,operation_id)",
    "CREATE INDEX IF NOT EXISTS configured_use_origins ON configured_component_uses(run_id,operation_key)",
    "CREATE INDEX IF NOT EXISTS configured_use_definitions ON configured_component_uses(run_id,json_extract(record_json,'$.definition_id'))",
    "CREATE TABLE IF NOT EXISTS inventory_diagnostics (run_id TEXT,message TEXT,PRIMARY KEY(run_id,message))",
]


def get_conversion_inventory(conn, run_id, operation_id, channel):
    """Read an operation's configured uses and the run's saved Java dependency graph."""
    from tools.state_store_tools.java_usage import check_detailed_scope
    check_detailed_scope(conn, run_id, {channel + '/' + operation_id})
    uses = [json.loads(row[0]) for row in conn.execute(
        "SELECT record_json FROM configured_component_uses WHERE run_id=? AND operation_id=? AND channel=?",
        (run_id, operation_id, channel))]
    from tools.state_store_tools.inventory_graph import graph_storage, reachable_ids
    _, normalized = graph_storage(conn, run_id)
    roots = {use['implementation_id'] for use in uses if use['implementation_id']}
    graph = get_java_dependency_graph(conn, run_id, include_uses=False, roots=roots if normalized else None)
    selected = roots | {edge.target_implementation_id for edge in graph.dependencies} if normalized else None
    implementations = {}
    clause = ' AND implementation_id IN (SELECT identity FROM graph_selected)' if normalized else ''
    for row in conn.execute("SELECT implementation_id,record_json FROM source_implementations WHERE run_id=?" + clause, (run_id,)):
        if selected is None or row[0] in selected:
            implementations[row[0]] = json.loads(row[1])
    return implementations, uses, graph.model_dump(mode='json')


def persist_component_inventory(conn, run_id, inventory, revision=None):
    """Replace one run snapshot atomically, including removal of obsolete usage records."""
    with conn:
        conn.execute("DELETE FROM java_dependency_uses WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM configured_component_uses WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM configured_component_definitions WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM source_implementations WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM java_dependency_edges WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM java_dependency_issues WHERE run_id=?", (run_id,))
        for table in ('java_usage_roots', 'java_usage_targets', 'java_usage_scope', 'java_usage_operations', 'java_direct_usage', 'configured_global_usage'):
            conn.execute('DELETE FROM ' + table + ' WHERE run_id=?', (run_id,))
        for implementation in inventory.implementations:
            conn.execute("INSERT INTO source_implementations VALUES (?, ?, ?, ?, ?)",
                         (run_id, implementation.implementation_id, inventory.workspace_id,
                          implementation.source_hash, implementation.model_dump_json()))
        for use in inventory.uses:
            conn.execute("INSERT INTO configured_component_uses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, use.use_id, use.implementation_id, use.operation_key, use.operation_id,
                 use.channel, use.component_kind, use.configuration_hash, use.model_dump_json()))
        for definition in inventory.definitions:
            conn.execute("INSERT INTO configured_component_definitions VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, definition.definition_id, definition.implementation_id, definition.component_kind,
                 definition.configuration_hash, definition.model_dump_json()))
        conn.execute('DELETE FROM inventory_diagnostics WHERE run_id=?', (run_id,))
        conn.executemany('INSERT OR IGNORE INTO inventory_diagnostics VALUES (?,?)', ((run_id, message) for message in inventory.diagnostics))
        conn.execute("INSERT OR REPLACE INTO component_inventory_reports VALUES (?, ?, ?, ?)",
                     (run_id, inventory.workspace_id, '[]', inventory.analysis_scope))
        graph = inventory.java_dependencies
        factors = getattr(graph, 'usage_factors', None)
        conn.execute("INSERT OR REPLACE INTO java_dependency_reports VALUES (?, ?)",
                     (run_id, json.dumps(dict(dependencies=[], issues=[], uses=[], storage='rows-v1',
                         usage_storage='factors-v1' if factors is not None else 'detailed',
                         direct_storage='counts-v1' if getattr(factors, 'mapped_direct_counts', False) else 'detailed', analysis_scope=graph.analysis_scope))))
        if factors is not None:
            if getattr(factors, 'mapped_direct_counts', False):
                conn.executemany('INSERT INTO java_direct_usage VALUES (?,?,?,?,?,?)',
                    ((run_id, *row) for row in factors.conn.execute("SELECT * FROM mapped_direct_counts WHERE target IN (SELECT identity FROM records WHERE collection='implementations')")))
                conn.executemany('INSERT INTO configured_global_usage VALUES (?,?,?,?,?,?)',
                    ((run_id, *row) for row in factors.conn.execute('SELECT * FROM mapped_definition_counts')))
            conn.executemany('INSERT INTO java_usage_roots VALUES (?,?,?,?,?,?)',
                ((run_id, *row) for row in factors.conn.execute('SELECT root,operation_key,operation_id,channel,weight FROM usage_roots')))
            conn.executemany('INSERT INTO java_usage_targets VALUES (?,?,?,?)',
                ((run_id, *row) for row in factors.conn.execute('SELECT root,target,count FROM usage_counts')))
            conn.executemany('INSERT INTO java_usage_scope VALUES (?,?)',
                ((run_id, row[0]) for row in factors.conn.execute('SELECT target FROM usage_targets')))
            conn.executemany('INSERT INTO java_usage_operations VALUES (?,?)',
                ((run_id, row[0]) for row in factors.conn.execute('SELECT consumer FROM requested_operations')))
        for edge in graph.dependencies:
            conn.execute('INSERT INTO java_dependency_edges VALUES (?,?,?,?,?)',
                (run_id, edge.dependency_id, edge.caller_implementation_id, edge.target_implementation_id, edge.model_dump_json()))
        from tools.component_inventory_tools.identity import stable_id
        for issue in graph.issues:
            conn.execute('INSERT OR REPLACE INTO java_dependency_issues VALUES (?,?,?,?)',
                (run_id, stable_id(issue.implementation_id, issue.message), issue.implementation_id, issue.model_dump_json()))
        for use in graph.uses:
            conn.execute("INSERT INTO java_dependency_uses VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (run_id, use.use_id, use.implementation_id, use.operation_key, use.operation_id, use.channel, use.model_dump_json()))
        if revision is not None:
            conn.execute('CREATE TABLE IF NOT EXISTS workspace_analysis_revision (run_id TEXT PRIMARY KEY,revision TEXT)')
            conn.execute('INSERT OR REPLACE INTO workspace_analysis_revision VALUES (?,?)', (run_id, revision))


def iter_implementation_usage(conn, run_id, *, selected_only=False):
    """Return exact reference counts and distinct original operation/channel consumers."""
    clause = " AND implementation_id IN (SELECT identity FROM conversion_scope WHERE run_id=? AND kind='implementation')" if selected_only else ''
    parameters = (run_id, run_id) if selected_only else (run_id,)
    from tools.state_store_tools.java_usage import factorized_usage, iter_global_java_usage, consumer_query
    if factorized_usage(conn, run_id) and not selected_only:
        # Unanalyzed targets must not be represented as having zero global consumers.
        clause = ' AND implementation_id IN (SELECT target FROM java_usage_scope WHERE run_id=?)'
        parameters = (run_id, run_id)
    indirect_consumers = consumer_query(conn, run_id)
    for row in conn.execute("SELECT implementation_id,record_json FROM source_implementations WHERE run_id=?" + clause + " ORDER BY implementation_id", parameters):
        identity = row[0]
        from tools.state_store_tools.java_usage import mapped_direct_usage, direct_consumer_query
        direct_count = (sum(int(value[0]) for value in conn.execute('SELECT weight FROM java_direct_usage WHERE run_id=? AND target=?', (run_id, identity)))
            if mapped_direct_usage(conn, run_id) else conn.execute('SELECT count(*) FROM configured_component_uses WHERE run_id=? AND implementation_id=?', (run_id, identity)).fetchone()[0])
        indirect_count = sum(use.reference_count for use in iter_global_java_usage(conn, run_id, implementation_id=identity))
        query = direct_consumer_query(conn, run_id) + ' UNION ' + indirect_consumers
        parameters = (run_id, identity, run_id, identity)
        operation_count, channel_count = conn.execute('SELECT count(DISTINCT operation_key),count(DISTINCT NULLIF(channel,\'\')) FROM (' + query + ')', parameters).fetchone()
        consumers = (dict(operation_key=key, operation_id=name, channel=channel) for key, name, channel in
                     conn.execute(query + ' ORDER BY operation_key', parameters))
        yield dict(implementation=json.loads(row[1]), reference_count=direct_count + indirect_count,
            direct_reference_count=direct_count, indirect_reference_count=indirect_count,
            operation_count=operation_count, channel_count=channel_count, consumers=consumers)


def get_implementation_usage(conn, run_id):
    """Keep the list API for callers that explicitly request a complete summary."""
    result = []
    for summary in iter_implementation_usage(conn, run_id):
        summary['consumers'] = list(summary['consumers'])
        result.append(summary)
    return result


def get_java_dependency_graph(conn, run_id, *, include_uses=True, roots=None):
    """Load a persisted source graph, preserving compatibility with earlier inventories."""
    from models.java_source_dependencies import JavaSourceDependencyGraph, JavaDependencyUse
    from tools.state_store_tools.inventory_graph import graph_rows
    graph = graph_rows(conn, run_id, roots=roots)
    if include_uses:
        from tools.state_store_tools.inventory_graph import graph_storage
        _, normalized = graph_storage(conn, run_id)
        clause = ' AND implementation_id IN (SELECT identity FROM graph_selected)' if roots is not None and normalized else ''
        graph.uses = [JavaDependencyUse.model_validate_json(row[0]) for row in conn.execute(
            "SELECT record_json FROM java_dependency_uses WHERE run_id=?" + clause + " ORDER BY use_id", (run_id,))]
    return graph


def iter_configured_component_usage(conn, run_id, *, selected_only=False):
    """Count configured definitions separately, retaining unused definitions with zero uses."""
    clause = ' AND definition_id IN (SELECT identity FROM report_definitions)' if selected_only else ''
    for row in conn.execute("SELECT definition_id,record_json FROM configured_component_definitions WHERE run_id=?" + clause + " ORDER BY definition_id", (run_id,)):
        from tools.state_store_tools.java_usage import mapped_direct_usage
        if mapped_direct_usage(conn, run_id):
            counts = conn.execute('SELECT count(DISTINCT operation_key),count(DISTINCT NULLIF(channel,\'\')) FROM configured_global_usage WHERE run_id=? AND definition=?', (run_id,row[0])).fetchone()
            total = sum(int(value[0]) for value in conn.execute('SELECT weight FROM configured_global_usage WHERE run_id=? AND definition=?', (run_id,row[0])))
            yield dict(definition=json.loads(row[1]),reference_count=total,operation_count=counts[0],channel_count=counts[1])
            continue
        counts = conn.execute('''SELECT count(*),count(DISTINCT operation_key),count(DISTINCT NULLIF(channel,''))
            FROM configured_component_uses WHERE run_id=? AND json_extract(record_json,'$.definition_id')=?''', (run_id, row[0])).fetchone()
        yield dict(definition=json.loads(row[1]), reference_count=counts[0], operation_count=counts[1], channel_count=counts[2])


def get_configured_component_usage(conn, run_id):
    """Keep the compatibility list API; report writers consume the iterator."""
    return list(iter_configured_component_usage(conn, run_id))
