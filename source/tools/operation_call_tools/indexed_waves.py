"""Calculate dependency waves and strongly connected groups with disk-backed traversal."""

import hashlib


def index_waves(conn):
    """Preserve the existing SCC/wave policy without retaining the operation graph in Python."""
    conn.executescript('''CREATE TABLE links(caller TEXT,target TEXT,PRIMARY KEY(caller,target));
        CREATE INDEX incoming_links ON links(target,caller);
        INSERT OR IGNORE INTO links SELECT caller,callee FROM calls;
        CREATE TABLE visited(node TEXT PRIMARY KEY);
        CREATE TABLE stack(ordinal INTEGER PRIMARY KEY AUTOINCREMENT,node TEXT,exiting INTEGER);
        CREATE TABLE finished(ordinal INTEGER PRIMARY KEY AUTOINCREMENT,node TEXT);
        CREATE TABLE assigned(node TEXT PRIMARY KEY,group_id INTEGER);
        CREATE INDEX group_members ON assigned(group_id,node);
        CREATE TABLE groups(group_id INTEGER PRIMARY KEY,first TEXT,cycle TEXT DEFAULT '',wave INTEGER,remaining INTEGER,done INTEGER DEFAULT 0);''')
    for (start,) in conn.execute('SELECT key FROM operations ORDER BY key'):
        if conn.execute('SELECT 1 FROM visited WHERE node=?',(start,)).fetchone():continue
        conn.execute('INSERT INTO stack(node,exiting) VALUES (?,0)',(start,))
        while row:=conn.execute('SELECT ordinal,node,exiting FROM stack ORDER BY ordinal DESC LIMIT 1').fetchone():
            ordinal,node,exiting=row;conn.execute('DELETE FROM stack WHERE ordinal=?',(ordinal,))
            if exiting:
                conn.execute('INSERT INTO finished(node) VALUES (?)',(node,))
            elif not conn.execute('SELECT 1 FROM visited WHERE node=?',(node,)).fetchone():
                conn.execute('INSERT INTO visited VALUES (?)',(node,))
                conn.execute('INSERT INTO stack(node,exiting) VALUES (?,1)',(node,))
                conn.execute('INSERT INTO stack(node,exiting) SELECT target,0 FROM links WHERE caller=? AND target NOT IN (SELECT node FROM visited) ORDER BY target DESC',(node,))
    group=0
    for (start,) in conn.execute('SELECT node FROM finished ORDER BY ordinal DESC'):
        if conn.execute('SELECT 1 FROM assigned WHERE node=?',(start,)).fetchone():continue
        group+=1;conn.execute('INSERT INTO assigned VALUES (?,?)',(start,group))
        conn.execute('INSERT INTO stack(node,exiting) VALUES (?,0)',(start,))
        while row:=conn.execute('SELECT ordinal,node FROM stack ORDER BY ordinal DESC LIMIT 1').fetchone():
            ordinal,node=row;conn.execute('DELETE FROM stack WHERE ordinal=?',(ordinal,))
            for (caller,) in conn.execute('SELECT caller FROM links WHERE target=? AND caller NOT IN (SELECT node FROM assigned) ORDER BY caller',(node,)):
                conn.execute('INSERT INTO assigned VALUES (?,?)',(caller,group))
                conn.execute('INSERT INTO stack(node,exiting) VALUES (?,0)',(caller,))
        conn.execute('INSERT INTO groups(group_id,first) SELECT ?,min(node) FROM assigned WHERE group_id=?',(group,group))
        cyclic=conn.execute('SELECT count(*) FROM assigned WHERE group_id=?',(group,)).fetchone()[0]>1 or conn.execute('SELECT 1 FROM links WHERE caller=? AND target=?',(start,start)).fetchone()
        if cyclic:
            digest=hashlib.sha256();first=True
            for (node,) in conn.execute('SELECT node FROM assigned WHERE group_id=? ORDER BY node',(group,)):
                if not first:digest.update(b'\n')
                digest.update(node.encode());first=False
            conn.execute('UPDATE groups SET cycle=? WHERE group_id=?',('cycle-'+digest.hexdigest()[:12],group))
    conn.executescript('''CREATE TABLE group_links(caller INTEGER,target INTEGER,PRIMARY KEY(caller,target));
        CREATE INDEX group_parents ON group_links(target,caller);
        INSERT OR IGNORE INTO group_links SELECT a.group_id,b.group_id FROM links e JOIN assigned a ON a.node=e.caller JOIN assigned b ON b.node=e.target WHERE a.group_id<>b.group_id;
        UPDATE groups SET remaining=(SELECT count(*) FROM group_links WHERE caller=groups.group_id);
        CREATE INDEX ready_groups ON groups(done,remaining,first);''')
    while row:=conn.execute('SELECT group_id FROM groups WHERE remaining=0 AND done=0 ORDER BY first LIMIT 1').fetchone():
        group=row[0]
        wave=conn.execute('SELECT COALESCE(max(g.wave),0)+1 FROM group_links l JOIN groups g ON g.group_id=l.target WHERE l.caller=?',(group,)).fetchone()[0]
        conn.execute('UPDATE groups SET wave=?,done=1 WHERE group_id=?',(wave,group))
        conn.execute('UPDATE groups SET remaining=remaining-1 WHERE group_id IN (SELECT caller FROM group_links WHERE target=?)',(group,))
    conn.executescript('''CREATE TABLE blocked(node TEXT PRIMARY KEY);
        INSERT INTO blocked WITH RECURSIVE reach(node) AS (SELECT i.operation FROM issues i JOIN operations o ON o.key=i.operation
            UNION SELECT l.caller FROM links l JOIN reach r ON l.target=r.node) SELECT node FROM reach;
        CREATE VIEW wave_rows AS SELECT o.key,o.channel,o.name,CASE WHEN b.node IS NULL THEN g.wave ELSE NULL END AS wave,g.cycle,
            CASE WHEN b.node IS NOT NULL THEN 'Unresolved dependency' WHEN g.cycle<>'' THEN 'Cycle requires coordinated contracts' ELSE '' END AS issue,
            (SELECT count(*) FROM links l WHERE l.caller=o.key) AS calls_count,(SELECT count(*) FROM links l WHERE l.target=o.key) AS callers_count
            FROM operations o JOIN assigned a ON a.node=o.key JOIN groups g ON g.group_id=a.group_id LEFT JOIN blocked b ON b.node=o.key;''')
