"""Resolve global Java syntax and spool exact operation consumers without a giant graph object."""

from pathlib import Path

from models.java_source_dependencies import JavaSourceDependency, JavaDependencyIssue, JavaDependencyUse
from models.stored_component_inventory import StoredJavaDependencyGraph
from tools.component_inventory_tools.identity import stable_id
from tools.component_inventory_tools.usage_propagation import prepare_root_counts
from tools.java_analysis_tools.source_dependencies.parser import iter_source_references
from tools.java_analysis_tools.source_dependencies.resolution import resolve_reference
from tools.state_store_tools.inventory_records import RecordSequence


def build_stored_java_dependencies(workspace, source_index, implementations, configured_uses, storage):
    """Keep global identities/counts exact while materializing only one reference/use at a time."""
    workspace = Path(workspace).resolve()
    by_path = {str((workspace / item.source_path).resolve()): item for item in implementations}
    edges = storage.mapping('dependencies', JavaSourceDependency)
    issues = storage.mapping('dependency_issues', JavaDependencyIssue)
    uses = storage.mapping('dependency_uses', JavaDependencyUse)
    conn = storage.conn
    conn.execute('CREATE TABLE graph_edges (identity TEXT PRIMARY KEY, caller TEXT, target TEXT)')
    conn.execute('CREATE INDEX graph_callers ON graph_edges(caller,identity)')
    conn.execute('CREATE INDEX graph_targets ON graph_edges(target,caller)')
    for document in iter_source_references(by_path, cache=storage.cache):
        path = str(Path(document.get('path')).resolve()) if document.get('path') else None
        caller = by_path.get(path)
        if document.tag == 'issue':
            if caller is None:
                raise ValueError('JDK parser reported an unscoped source error: ' + document.get('message'))
            issue = JavaDependencyIssue(implementation_id=caller.implementation_id, message='Java syntax: ' + document.get('message'))
            issues[stable_id(issue.implementation_id, issue.message)] = issue
            continue
        if caller is None:
            continue
        for reference in document.findall('reference'):
            targets, message = resolve_reference(reference, document, source_index, path,
                                                  owner_project=source_index.class_projects.get(path))
            if message:
                issue = JavaDependencyIssue(implementation_id=caller.implementation_id, message=message)
                issues[stable_id(issue.implementation_id, message)] = issue
            for target_path in targets:
                target = by_path.get(target_path)
                if target is None:
                    target = by_path.get(str(Path(target_path).resolve()))
                if target is None or target.implementation_id == caller.implementation_id:
                    continue
                offset = int(reference.get('offset'))
                identity = stable_id(caller.implementation_id, target.implementation_id, offset)
                edges[identity] = JavaSourceDependency(dependency_id=identity, caller_implementation_id=caller.implementation_id,
                    target_implementation_id=target.implementation_id, source_offset=offset,
                    reference_kind=reference.get('kind'), reference_name=reference.get('name'))
                conn.execute('INSERT OR REPLACE INTO graph_edges VALUES (?,?,?)', (identity, caller.implementation_id, target.implementation_id))
    for use in configured_uses:
        if not use.implementation_id or use.resolution_issue:
            continue
        prepare_root_counts(conn, use.implementation_id)
        for edge, target, count in conn.execute('''SELECT e.identity,e.target,c.count FROM root_edge_counts c
            JOIN graph_edges e ON e.identity=c.edge WHERE c.root=? ORDER BY e.identity''', (use.implementation_id,)):
            identity = stable_id(use.use_id, edge)
            uses[identity] = JavaDependencyUse(use_id=identity, source_use_id=use.use_id, dependency_id=edge,
                operation_key=use.operation_key, operation_id=use.operation_id, channel=use.channel,
                implementation_id=target, reference_count=int(count))
    return StoredJavaDependencyGraph(dependencies=RecordSequence(edges), uses=RecordSequence(uses), issues=RecordSequence(issues))
