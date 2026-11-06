"""Propagate exact reference multiplicities with disk-backed reachability and work queues."""


def prepare_root_counts(conn, root):
    """Cache one root's edge multiplicities, preserving legacy cycle fallback ordering."""
    conn.execute('CREATE TABLE IF NOT EXISTS root_count_ready (root TEXT PRIMARY KEY)')
    conn.execute('CREATE TABLE IF NOT EXISTS root_edge_counts (root TEXT, edge TEXT, count TEXT, PRIMARY KEY(root,edge))')
    if conn.execute('SELECT 1 FROM root_count_ready WHERE root=?', (root,)).fetchone():
        return
    # executescript would commit the previous root on every call, causing thousands
    # of unnecessary disk flushes when many consumers share a small helper closure.
    for statement in (
        'CREATE TEMP TABLE IF NOT EXISTS reachable (node TEXT PRIMARY KEY)',
        'CREATE TEMP TABLE IF NOT EXISTS remaining_degree (node TEXT PRIMARY KEY, degree INTEGER)',
        'CREATE TEMP TABLE IF NOT EXISTS traversal_order (ordinal INTEGER PRIMARY KEY, node TEXT)',
        'CREATE TEMP TABLE IF NOT EXISTS path_counts (node TEXT PRIMARY KEY, count TEXT)',
        'DELETE FROM reachable','DELETE FROM remaining_degree','DELETE FROM traversal_order','DELETE FROM path_counts',
    ):
        conn.execute(statement)
    conn.execute('''INSERT INTO reachable WITH RECURSIVE reach(node) AS (
        SELECT ? UNION SELECT e.target FROM graph_edges e JOIN reach r ON e.caller=r.node)
        SELECT node FROM reach''', (root,))
    conn.execute('''INSERT INTO remaining_degree SELECT r.node,count(DISTINCT e.target)
        FROM reachable r LEFT JOIN graph_edges e ON e.caller=r.node GROUP BY r.node''')
    conn.execute('CREATE INDEX IF NOT EXISTS degree_order ON remaining_degree(degree,node)')
    while True:
        ready = conn.execute('SELECT node FROM remaining_degree WHERE degree=0 ORDER BY node LIMIT 1').fetchone()
        if ready is None:
            break
        node = ready[0]
        conn.execute('INSERT INTO traversal_order(node) VALUES (?)', (node,))
        conn.execute('DELETE FROM remaining_degree WHERE node=?', (node,))
        conn.execute('''UPDATE remaining_degree SET degree=degree-1 WHERE EXISTS
            (SELECT 1 FROM graph_edges e WHERE e.target=? AND e.caller=remaining_degree.node)''', (node,))
    cyclic = conn.execute('SELECT 1 FROM remaining_degree LIMIT 1').fetchone() is not None
    if cyclic:
        conn.execute("INSERT INTO path_counts SELECT node,'1' FROM reachable")
        nodes = conn.execute('SELECT node FROM reachable ORDER BY node')
    else:
        conn.execute('INSERT INTO path_counts VALUES (?,?)', (root, '1'))
        nodes = conn.execute('SELECT node FROM traversal_order ORDER BY ordinal DESC')
    for (caller,) in nodes:
        row = conn.execute('SELECT count FROM path_counts WHERE node=?', (caller,)).fetchone()
        count = int(row[0]) if row else 0
        for edge, target in conn.execute('SELECT identity,target FROM graph_edges WHERE caller=? ORDER BY identity', (caller,)):
            conn.execute('INSERT INTO root_edge_counts VALUES (?,?,?)', (root, edge, str(max(count, 1))))
            prior = conn.execute('SELECT count FROM path_counts WHERE node=?', (target,)).fetchone()
            conn.execute('INSERT OR REPLACE INTO path_counts VALUES (?,?)', (target, str((int(prior[0]) if prior else 0) + count)))
    conn.execute('INSERT INTO root_count_ready VALUES (?)', (root,))
