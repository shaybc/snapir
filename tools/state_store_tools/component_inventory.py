"""Persist authoritative implementation identities and configured-use evidence per run."""

import json


INVENTORY_SCHEMA = [
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
]


def persist_component_inventory(conn, run_id, inventory):
    """Replace one run snapshot atomically, including removal of obsolete usage records."""
    with conn:
        conn.execute("DELETE FROM java_dependency_uses WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM configured_component_uses WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM configured_component_definitions WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM source_implementations WHERE run_id=?", (run_id,))
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
        conn.execute("INSERT OR REPLACE INTO component_inventory_reports VALUES (?, ?, ?, ?)",
                     (run_id, inventory.workspace_id, json.dumps(inventory.diagnostics), inventory.analysis_scope))
        graph = inventory.java_dependencies
        conn.execute("INSERT OR REPLACE INTO java_dependency_reports VALUES (?, ?)",
                     (run_id, graph.model_copy(update={"uses": []}).model_dump_json()))
        for use in graph.uses:
            conn.execute("INSERT INTO java_dependency_uses VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (run_id, use.use_id, use.implementation_id, use.operation_key, use.operation_id, use.channel, use.model_dump_json()))


def get_implementation_usage(conn, run_id):
    """Return exact reference counts and distinct original operation/channel consumers."""
    summaries = []
    for row in conn.execute("SELECT implementation_id,record_json FROM source_implementations WHERE run_id=? ORDER BY implementation_id", (run_id,)):
        uses = conn.execute("SELECT operation_key,operation_id,channel FROM configured_component_uses WHERE run_id=? AND implementation_id=?",
                            (run_id, row[0])).fetchall()
        indirect = conn.execute("SELECT operation_key,operation_id,channel,record_json FROM java_dependency_uses WHERE run_id=? AND implementation_id=?",
                                (run_id, row[0])).fetchall()
        direct_count = len(uses)
        indirect_count = sum(json.loads(use[3]).get("reference_count", 1) for use in indirect)
        uses = [*uses, *(tuple(use[:3]) for use in indirect)]
        consumers = {(use[0], use[1], use[2]) for use in uses}
        summaries.append(dict(implementation=json.loads(row[1]), reference_count=direct_count + indirect_count,
            direct_reference_count=direct_count, indirect_reference_count=indirect_count,
            operation_count=len({use[0] for use in consumers}), channel_count=len({use[2] for use in consumers if use[2]}),
            consumers=[dict(operation_key=key, operation_id=name, channel=channel)
                       for key, name, channel in sorted(consumers, key=lambda value: value[0])]))
    return summaries


def get_java_dependency_graph(conn, run_id, *, include_uses=True):
    """Load a persisted source graph, preserving compatibility with earlier inventories."""
    from models.java_source_dependencies import JavaSourceDependencyGraph, JavaDependencyUse
    row = conn.execute("SELECT graph_json FROM java_dependency_reports WHERE run_id=?", (run_id,)).fetchone()
    graph = JavaSourceDependencyGraph.model_validate_json(row[0]) if row else JavaSourceDependencyGraph()
    if include_uses:
        graph.uses = [JavaDependencyUse.model_validate_json(row[0]) for row in conn.execute(
            "SELECT record_json FROM java_dependency_uses WHERE run_id=? ORDER BY use_id", (run_id,))]
    return graph


def get_configured_component_usage(conn, run_id):
    """Count configured definitions separately, retaining unused definitions with zero uses."""
    counts = {}
    for row in conn.execute("SELECT record_json FROM configured_component_uses WHERE run_id=?", (run_id,)):
        use = json.loads(row[0])
        counts.setdefault(use["definition_id"], []).append(use)
    result = []
    for row in conn.execute("SELECT definition_id,record_json FROM configured_component_definitions WHERE run_id=? ORDER BY definition_id", (run_id,)):
        uses = counts.get(row[0], [])
        result.append(dict(definition=json.loads(row[1]), reference_count=len(uses),
            operation_count=len({use["operation_key"] for use in uses}),
            channel_count=len({use["channel"] for use in uses if use["channel"]})))
    return result
