"""Reuse persisted Java edges and global consumer factors; expand selected detail only."""

from collections import OrderedDict
from pathlib import Path

from models.java_source_dependencies import JavaSourceDependency, JavaDependencyIssue, JavaDependencyUse
from models.stored_component_inventory import StoredJavaDependencyGraph
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.inventory_records import RecordSequence


class BoundedCache(OrderedDict):
    """Cap small lookup memoization even for a selected closure covering the whole workspace."""

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
        if len(self) > 256:
            self.popitem(last=False)


def build_mapped_graph(storage, implementations, configured_uses):
    """Keep the global graph in SQLite and use the existing exact multiplicity algorithm."""
    mapped, conn = storage.mapped_analysis, storage.conn
    source, workspace_id = mapped.analysis.conn, mapped.analysis['workspace_id']
    conn.execute('ATTACH DATABASE ? AS mapper_snapshot', (mapped.analysis.database.as_uri()+'?mode=ro&immutable=1',))
    conn.executescript('''CREATE TABLE mapped_implementations(file TEXT PRIMARY KEY,identity TEXT);
        CREATE TABLE graph_edges(identity TEXT PRIMARY KEY,caller TEXT,target TEXT);
        CREATE INDEX graph_callers ON graph_edges(caller,identity);
        CREATE INDEX graph_targets ON graph_edges(target,caller);
        CREATE TABLE mapped_global_roots(root TEXT,operation_key TEXT,operation_id TEXT,channel TEXT,weight TEXT,direct_weight TEXT);
        CREATE TABLE mapped_direct_counts(target TEXT,operation_key TEXT,operation_id TEXT,channel TEXT,weight TEXT);
        CREATE TABLE mapped_definition_counts(definition TEXT,operation_key TEXT,operation_id TEXT,channel TEXT,weight TEXT);
        CREATE TABLE xml_definitions(kind TEXT,name TEXT,data TEXT);''')
    # Metadata only: no source body, AST, or Markdown is loaded for these global IDs.
    for file, fqcn, root, relative in source.execute('SELECT s.file,s.fqcn,s.root,f.relative_path FROM java_sources s JOIN files f ON f.path=s.file ORDER BY s.file'):
        identity = stable_id(workspace_id,Path(root).relative_to(mapped.analysis.source_root).as_posix(),relative,fqcn,None)
        conn.execute('INSERT INTO mapped_implementations VALUES (?,?)', (file, identity))
    conn.create_function('mapped_edge_id',3,lambda caller,target,offset:stable_id(caller,target,offset),deterministic=True)
    conn.execute('''INSERT INTO graph_edges SELECT mapped_edge_id(c.identity,t.identity,e.offset),c.identity,t.identity
        FROM mapper_snapshot.java_edges e JOIN mapped_implementations c ON c.file=e.caller JOIN mapped_implementations t ON t.file=e.target''')
    for operation, implementation, weight, direct, name, channel, relative, selector in source.execute('''SELECT r.operation,r.implementation,r.weight,r.direct_weight,d.name,d.channel,f.relative_path,d.selector
        FROM operation_roots r JOIN canonical_definitions d ON d.node=r.operation JOIN files f ON f.path=d.file ORDER BY r.operation,r.implementation'''):
        root = conn.execute('SELECT identity FROM mapped_implementations WHERE file=?', (implementation,)).fetchone()[0]
        key = stable_id(workspace_id, relative, selector)
        conn.execute('INSERT INTO mapped_global_roots VALUES (?,?,?,?,?,?)', (root,key,name,channel,str(weight),str(direct)))
        conn.execute('INSERT INTO mapped_direct_counts VALUES (?,?,?,?,?)', (root,key,name,channel,str(direct)))
    issues = storage.mapping('dependency_issues', JavaDependencyIssue)
    for collection in ('dependency_issues', 'java_issues'):
        for file, message in source.execute("SELECT json_extract(r.data,'$.file'),json_extract(r.data,'$.message') FROM records r JOIN selected_java s ON s.file=json_extract(r.data,'$.file') WHERE r.collection=?", (collection,)):
            owner = conn.execute('SELECT identity FROM mapped_implementations WHERE file=?', (file,)).fetchone()
            if owner:
                issue = JavaDependencyIssue(implementation_id=owner[0], message=message)
                issues[stable_id(owner[0], message)] = issue
    uses = storage.mapping('dependency_uses', JavaDependencyUse)
    from tools.component_inventory_tools.segmented_java_usage import build_segmented_usage
    factors = build_segmented_usage(storage, implementations, uses)
    factors.mapped_direct_counts = True
    # Only selected configured definitions need global summaries; XML bodies remain in the map.
    for node_file, selector, name, channel, operation_file, operation_selector, weight in source.execute('''SELECT n.file,n.selector,o.name,o.channel,f.relative_path,o.selector,c.weight
        FROM configured_counts c JOIN xml_nodes n ON n.id=c.node JOIN canonical_definitions o ON o.node=c.operation JOIN files f ON f.path=o.file'''):
        relative = Path(node_file).relative_to(mapped.analysis.source_root).as_posix()
        definition = stable_id(workspace_id, relative, selector)
        if conn.execute("SELECT 1 FROM records WHERE collection='definitions' AND identity=?", (definition,)).fetchone():
            conn.execute('INSERT INTO mapped_definition_counts VALUES (?,?,?,?,?)',
                (definition,stable_id(workspace_id,operation_file,operation_selector),name,channel,str(weight)))
    edges = storage.mapping('dependencies', JavaSourceDependency)
    conn.execute('CREATE TEMP TABLE mapped_selected_files(file TEXT PRIMARY KEY)')
    conn.executemany('INSERT INTO mapped_selected_files VALUES (?)',source.execute('SELECT file FROM selected_java'))
    for caller_id, target_id, offset, kind, name in conn.execute('''SELECT c.identity,t.identity,e.offset,e.kind,e.name FROM mapper_snapshot.java_edges e
        JOIN mapped_selected_files s ON s.file=e.caller JOIN mapped_implementations c ON c.file=e.caller
        JOIN mapped_implementations t ON t.file=e.target ORDER BY e.caller,e.target,e.offset'''):
        identity = stable_id(caller_id, target_id, offset)
        edges[identity] = JavaSourceDependency(dependency_id=identity,caller_implementation_id=caller_id,
            target_implementation_id=target_id,source_offset=offset,reference_kind=kind,reference_name=name)
    graph = StoredJavaDependencyGraph(dependencies=RecordSequence(edges), uses=RecordSequence(uses), issues=RecordSequence(issues),
        analysis_scope='Persisted global mapper graph; selected operation/dependency detail and exact original-consumer factors')
    graph.usage_factors = factors
    return graph
