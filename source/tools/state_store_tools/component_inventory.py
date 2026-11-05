"""Persist authoritative implementation identities and configured-use evidence per run."""

import json


INVENTORY_SCHEMA = [
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
        conn.execute("INSERT OR REPLACE INTO java_dependency_reports VALUES (?, ?)",
                     (run_id, json.dumps(dict(dependencies=[], issues=[], uses=[], storage='rows-v1', analysis_scope=graph.analysis_scope))))
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
    for row in conn.execute("SELECT implementation_id,record_json FROM source_implementations WHERE run_id=?" + clause + " ORDER BY implementation_id", parameters):
        identity = row[0]
        direct_count = conn.execute('SELECT count(*) FROM configured_component_uses WHERE run_id=? AND implementation_id=?', (run_id, identity)).fetchone()[0]
        indirect_count = sum(json.loads(use[0]).get('reference_count', 1) for use in conn.execute(
            'SELECT record_json FROM java_dependency_uses WHERE run_id=? AND implementation_id=?', (run_id, identity)))
        query = '''SELECT operation_key,operation_id,channel FROM configured_component_uses WHERE run_id=? AND implementation_id=?
            UNION SELECT operation_key,operation_id,channel FROM java_dependency_uses WHERE run_id=? AND implementation_id=?'''
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
        counts = conn.execute('''SELECT count(*),count(DISTINCT operation_key),count(DISTINCT NULLIF(channel,''))
            FROM configured_component_uses WHERE run_id=? AND json_extract(record_json,'$.definition_id')=?''', (run_id, row[0])).fetchone()
        yield dict(definition=json.loads(row[1]), reference_count=counts[0], operation_count=counts[1], channel_count=counts[2])


def get_configured_component_usage(conn, run_id):
    """Keep the compatibility list API; report writers consume the iterator."""
    return list(iter_configured_component_usage(conn, run_id))
