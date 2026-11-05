"""Expose selected detailed report records while retaining exact global usage counts in SQLite."""

from models.component_usage import ConfiguredComponentDefinition, ConfiguredComponentUse
from models.java_source_dependencies import JavaDependencyUse, JavaDependencyIssue, JavaSourceDependency
from models.source_component_identity import SourceImplementationRecord
from models.stored_component_inventory import StoredComponentInventory, StoredJavaDependencyGraph


def selected_inventory(conn, run_id, inventory):
    """Build lazy report views; unrelated source bodies and use details stay in the database."""
    selected_implementations = "SELECT identity FROM conversion_scope WHERE run_id=? AND kind='implementation'"
    selected_operations = "SELECT identity FROM conversion_scope WHERE run_id=? AND kind='operation'"
    conn.execute('CREATE TEMP TABLE IF NOT EXISTS report_definitions (identity TEXT PRIMARY KEY)')
    conn.execute('DELETE FROM report_definitions')
    conn.execute('''INSERT OR IGNORE INTO report_definitions SELECT json_extract(record_json,'$.definition_id')
        FROM configured_component_uses WHERE run_id=? AND COALESCE(channel,'')||'/'||operation_id IN (''' + selected_operations + ')', (run_id, run_id))
    conn.execute('''INSERT OR IGNORE INTO report_definitions SELECT definition_id FROM configured_component_definitions
        WHERE run_id=? AND component_kind='operation' AND COALESCE(json_extract(record_json,'$.channel'),'')||'/'||
        json_extract(record_json,'$.logical_id') IN (''' + selected_operations + ')', (run_id, run_id))

    def records(query, model, parameters):
        for (record,) in conn.execute(query, parameters):
            yield model.model_validate_json(record)

    graph_scope = 'Selected operation dependency closure; complete workspace graph and exact global consumers are retained in SQLite'

    def graph_view():
        # Generators are single-pass: the separate graph report gets its own view.
        return StoredJavaDependencyGraph(
            dependencies=records('SELECT record_json FROM java_dependency_edges WHERE run_id=? AND caller IN (' + selected_implementations + ') ORDER BY dependency_id', JavaSourceDependency, (run_id, run_id)),
            issues=records('SELECT record_json FROM java_dependency_issues WHERE run_id=? AND implementation_id IN (' + selected_implementations + ') ORDER BY issue_id', JavaDependencyIssue, (run_id, run_id)),
            uses=records("SELECT record_json FROM java_dependency_uses WHERE run_id=? AND COALESCE(channel,'')||'/'||operation_id IN (" + selected_operations + ') ORDER BY use_id', JavaDependencyUse, (run_id, run_id)),
            analysis_scope=graph_scope)

    result = StoredComponentInventory(workspace_id=inventory.workspace_id,
        implementations=records('SELECT record_json FROM source_implementations WHERE run_id=? AND implementation_id IN (' + selected_implementations + ') ORDER BY implementation_id', SourceImplementationRecord, (run_id, run_id)),
        definitions=records('SELECT record_json FROM configured_component_definitions WHERE run_id=? AND definition_id IN (SELECT identity FROM report_definitions) ORDER BY definition_id', ConfiguredComponentDefinition, (run_id,)),
        uses=records("SELECT record_json FROM configured_component_uses WHERE run_id=? AND COALESCE(channel,'')||'/'||operation_id IN (" + selected_operations + ') ORDER BY use_id', ConfiguredComponentUse, (run_id, run_id)),
        diagnostics=inventory.diagnostics, java_dependencies=graph_view(),
        analysis_scope='Selected operation dependency closure; diagnostics are global; complete global metadata and sharing counts remain in SQLite')
    return result, graph_view
