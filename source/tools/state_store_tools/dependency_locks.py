"""Persist run-wide version choices atomically while retaining earlier policy histories."""
import json
from tools.state_store_tools._json import utc_now


def initialize(conn):
    """Create a policy-versioned lock table without rewriting historical conversion records."""
    conn.execute('''CREATE TABLE IF NOT EXISTS conversion_dependency_locks (
        run_id TEXT NOT NULL, policy_hash TEXT NOT NULL, group_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
        version TEXT NOT NULL, dependency_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(run_id,policy_hash,group_id,artifact_id))''')


def read(conn,run_id,policy_hash):
    """Return the exact choices shared by independent branches of this target run."""
    initialize(conn)
    return [json.loads(row[0]) for row in conn.execute('SELECT dependency_json FROM conversion_dependency_locks WHERE run_id=? AND policy_hash=? ORDER BY group_id,artifact_id',(run_id,policy_hash))]


def remember(conn,run_id,policy_hash,dependencies):
    """Reject competing choices under one lock; a new approved policy gets a new namespace."""
    initialize(conn);conn.execute('SAVEPOINT dependency_lock')
    try:
        for dependency in dependencies:
            item=dependency.model_dump(mode='json');key=(run_id,policy_hash,dependency.group_id,dependency.artifact_id)
            conn.execute('INSERT OR IGNORE INTO conversion_dependency_locks VALUES (?,?,?,?,?,?,?)',(*key,dependency.version,json.dumps(item,sort_keys=True),utc_now()))
            row=conn.execute('SELECT version FROM conversion_dependency_locks WHERE run_id=? AND policy_hash=? AND group_id=? AND artifact_id=?',key).fetchone()
            if row[0]!=dependency.version:raise ValueError('Shared dependency lock conflict: '+dependency.group_id+':'+dependency.artifact_id+' requires '+row[0]+', proposed '+dependency.version)
        conn.execute('RELEASE SAVEPOINT dependency_lock')
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT dependency_lock');conn.execute('RELEASE SAVEPOINT dependency_lock');raise
