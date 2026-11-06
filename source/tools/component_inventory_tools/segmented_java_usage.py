"""Keep global consumer counts factorized and expand detailed Java uses only for requested work."""

from tools.component_inventory_tools.identity import stable_id
from tools.component_inventory_tools.operation_selection import select_stored_operations
from tools.component_inventory_tools.dependency_order import dependency_first_order
from tools.component_inventory_tools.usage_propagation import prepare_root_counts
from models.java_source_dependencies import JavaDependencyUse

COMPACT_GRAPH_EDGE_LIMIT = 100000


class UsageFactors:
    """Expose compact scratch tables to the authoritative run-database writer."""

    def __init__(self, conn):
        self.conn = conn


def build_segmented_usage(storage, implementations, uses):
    """Preserve exact global multiplicities without global operation-times-edge records."""
    conn, progress = storage.conn, storage.progress
    mapped = getattr(storage, 'mapped_analysis', None)
    if mapped is None:
        _, required, _, _ = select_stored_operations(storage, implementations)
    conn.executescript('''
        CREATE TEMP TABLE requested_operations (consumer TEXT PRIMARY KEY);
        CREATE TABLE usage_roots (root TEXT, operation_key TEXT, operation_id TEXT, channel TEXT, weight INTEGER);
        CREATE INDEX usage_root_ids ON usage_roots(root);
        CREATE TABLE usage_targets (target TEXT PRIMARY KEY);
        CREATE TABLE usage_counts (root TEXT,target TEXT,count TEXT,PRIMARY KEY(root,target));
        CREATE TABLE usage_details (root TEXT,edge TEXT,count TEXT,PRIMARY KEY(root,edge));
        CREATE TABLE usage_caller_counts (root TEXT,caller TEXT,count TEXT,PRIMARY KEY(root,caller));
    ''')
    if mapped is None:
        conn.executemany('INSERT INTO requested_operations VALUES (?)', ((channel + '/' + name,) for channel, name in required))
    else:
        conn.executemany('INSERT INTO requested_operations VALUES (?)', mapped.analysis.conn.execute('SELECT o.channel||\'/\'||o.name FROM operation_context_index o JOIN selected_contexts s ON s.identity=o.identity'))
    valid = "collection='uses' AND json_extract(data,'$.implementation_id') IS NOT NULL AND json_extract(data,'$.resolution_issue') IS NULL"
    if getattr(storage, 'mapped_analysis', None) is not None:
        conn.execute('INSERT INTO usage_roots SELECT root,operation_key,operation_id,channel,weight FROM mapped_global_roots WHERE CAST(weight AS INTEGER)>0')
    else:
        conn.execute('''INSERT INTO usage_roots SELECT json_extract(data,'$.implementation_id'),json_extract(data,'$.operation_key'),
        json_extract(data,'$.operation_id'),json_extract(data,'$.channel'),count(*) FROM records WHERE ''' + valid + '''
        GROUP BY json_extract(data,'$.implementation_id'),json_extract(data,'$.operation_key'),json_extract(data,'$.operation_id'),json_extract(data,'$.channel')''')
    requested = "COALESCE(json_extract(data,'$.channel'),'')||'/'||json_extract(data,'$.operation_id') IN (SELECT consumer FROM requested_operations)"
    conn.execute('CREATE TEMP TABLE requested_roots (root TEXT PRIMARY KEY)')
    conn.execute("INSERT INTO requested_roots SELECT DISTINCT json_extract(data,'$.implementation_id') FROM records WHERE " + valid + ' AND ' + requested)
    roots = {row[0] for row in conn.execute('SELECT root FROM requested_roots')} if mapped is None else None
    conn.execute('''INSERT INTO usage_targets WITH RECURSIVE reach(node) AS (
        SELECT root FROM requested_roots UNION SELECT e.target FROM graph_edges e JOIN reach r ON e.caller=r.node)
        SELECT node FROM reach''')
    targets = {row[0] for row in conn.execute('SELECT target FROM usage_targets')} if mapped is None else None
    conn.execute('''CREATE TEMP TABLE relevant_roots AS WITH RECURSIVE reach(node) AS (
        SELECT target FROM usage_targets UNION SELECT e.caller FROM graph_edges e JOIN reach r ON e.target=r.node)
        SELECT DISTINCT root FROM usage_roots WHERE root IN (SELECT node FROM reach)''')
    conn.execute('DELETE FROM usage_roots WHERE root NOT IN (SELECT root FROM relevant_roots)')
    root_count = conn.execute('SELECT count(*) FROM relevant_roots').fetchone()[0]
    if progress:
        progress.stage('Computing compact global sharing counts for selected targets', root_count)
    # Bounded compact adjacency avoids millions of per-node SQL statements on ordinary graphs.
    outgoing = None
    link_count = conn.execute('SELECT count(*) FROM (SELECT caller,target FROM graph_edges GROUP BY caller,target)').fetchone()[0]
    if link_count <= COMPACT_GRAPH_EDGE_LIMIT and getattr(storage, 'mapped_analysis', None) is None:
        outgoing = {}
        for caller, target, sites in conn.execute('SELECT caller,target,count(*) FROM graph_edges GROUP BY caller,target ORDER BY caller,target'):
            outgoing.setdefault(caller, []).append((target, sites))

    def compact_counts(root):
        visited, pending = set(), [root]
        while pending:
            caller = pending.pop()
            if caller not in visited:
                visited.add(caller)
                pending.extend(target for target, _ in outgoing.get(caller, ()))
        dependencies = {caller: {target for target, _ in outgoing.get(caller, ())} for caller in visited}
        try:
            order = reversed(dependency_first_order(visited, dependencies))
            counts = {root: 1}
        except ValueError:
            order = sorted(visited)
            counts = {caller: 1 for caller in visited}
        for caller in order:
            count = counts.get(caller, 0)
            for target, sites in outgoing.get(caller, ()):
                yield None, caller, target, max(count, 1), sites
                counts[target] = counts.get(target, 0) + count * sites

    class ExactSum:
        """Aggregate arbitrary-size multiplicities without SQLite integer overflow."""
        def __init__(self): self.total = 0
        def step(self, value): self.total += int(value)
        def finalize(self): return str(self.total)

    if mapped is not None:
        conn.create_aggregate('exact_usage_sum',1,ExactSum)
    for (root,) in conn.execute('SELECT root FROM relevant_roots ORDER BY root'):
        if progress:
            progress.current('global reference multiplicities for root=' + root)
        if mapped is not None:
            prepare_root_counts(conn,root)
            conn.execute('''INSERT INTO usage_counts SELECT ?,e.target,exact_usage_sum(c.count)
                FROM root_edge_counts c JOIN graph_edges e ON e.identity=c.edge
                JOIN usage_targets t ON t.target=e.target WHERE c.root=? GROUP BY e.target''',(root,root))
            if conn.execute('SELECT 1 FROM requested_roots WHERE root=?',(root,)).fetchone():
                conn.execute('INSERT INTO usage_details SELECT root,edge,count FROM root_edge_counts WHERE root=?',(root,))
            conn.execute('DELETE FROM root_edge_counts WHERE root=?',(root,))
            if progress:
                progress.advance(detail='Stored exact selected-target multiplicities; root='+root)
            continue
        summary = {}
        if outgoing is None:
            prepare_root_counts(conn, root)
            counts = conn.execute('''SELECT e.identity,e.caller,e.target,c.count,1 FROM root_edge_counts c JOIN graph_edges e
                ON e.identity=c.edge WHERE c.root=? ORDER BY e.identity''', (root,))
        else:
            counts = compact_counts(root)
        for edge, caller, target, count, sites in counts:
            count = int(count)
            if target in targets:
                summary[target] = summary.get(target, 0) + count * sites
            if root in roots:
                if outgoing is None:
                    conn.execute('INSERT INTO usage_details VALUES (?,?,?)', (root, edge, str(count)))
                else:
                    conn.execute('INSERT OR IGNORE INTO usage_caller_counts VALUES (?,?,?)', (root, caller, str(count)))
        if root in roots and outgoing is not None:
            conn.execute('''INSERT INTO usage_details SELECT c.root,e.identity,c.count FROM usage_caller_counts c
                JOIN graph_edges e ON e.caller=c.caller WHERE c.root=?''', (root,))
        conn.executemany('INSERT INTO usage_counts VALUES (?,?,?)', ((root, target, str(count)) for target, count in summary.items()))
        if outgoing is None:
            conn.execute('DELETE FROM root_edge_counts WHERE root=?', (root,))
        if progress:
            progress.advance(detail=f'{len(summary)} selected targets; root={root}')
    if progress:
        total = conn.execute('SELECT count(*) FROM records WHERE ' + valid + ' AND ' + requested).fetchone()[0]
        progress.stage('Expanding Java-use evidence for selected/required operations only', total)
    for (identity,) in conn.execute('SELECT identity FROM records WHERE ' + valid + ' AND ' + requested + ' ORDER BY identity'):
        from models.component_usage import ConfiguredComponentUse
        use = storage.mapping('uses', ConfiguredComponentUse)[identity]
        for edge, target, count in conn.execute('''SELECT e.identity,e.target,d.count FROM usage_details d
            JOIN graph_edges e ON e.identity=d.edge WHERE d.root=? ORDER BY e.identity''', (use.implementation_id,)):
            key = stable_id(use.use_id, edge)
            uses[key] = JavaDependencyUse(use_id=key, source_use_id=use.use_id, dependency_id=edge,
                operation_key=use.operation_key, operation_id=use.operation_id, channel=use.channel,
                implementation_id=target, reference_count=int(count))
        if progress:
            progress.advance(detail=(use.channel or '') + '/' + use.operation_id)
    return UsageFactors(conn)
