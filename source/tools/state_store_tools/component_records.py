"""Additive immutable component revisions and mutable heads; callers own outer transactions."""
from contextlib import contextmanager
import json
import uuid
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def initialize(conn):
    """Keep component progress out of unit-acceptance tables and legacy cache categories."""
    conn.execute('''CREATE TABLE IF NOT EXISTS conversion_component_plans (
        run_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, plan_json TEXT NOT NULL, target_json TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS conversion_component_heads (
        run_id TEXT NOT NULL, group_id TEXT NOT NULL, input_revision TEXT NOT NULL, status TEXT NOT NULL,
        contract_revision TEXT, result_revision TEXT, PRIMARY KEY(run_id,group_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS conversion_component_records (
        run_id TEXT NOT NULL, group_id TEXT NOT NULL, category TEXT NOT NULL, revision TEXT NOT NULL,
        record_json TEXT NOT NULL, record_hash TEXT NOT NULL, PRIMARY KEY(run_id,group_id,category,revision))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS conversion_component_links (
        run_id TEXT NOT NULL, consumer_group TEXT NOT NULL, dependency_group TEXT NOT NULL,
        PRIMARY KEY(run_id,consumer_group,dependency_group))''')


@contextmanager
def transaction(conn):
    """An inner savepoint must never commit a surrounding scoped-preparation transaction."""
    name='component_'+uuid.uuid4().hex
    conn.execute('SAVEPOINT '+name)
    try:
        initialize(conn)
        yield
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT '+name);conn.execute('RELEASE SAVEPOINT '+name)
        raise
    conn.execute('RELEASE SAVEPOINT '+name)


def head(conn,run_id,group_id):
    """Read current progress without reinterpreting it as unit acceptance."""
    row=conn.execute('SELECT * FROM conversion_component_heads WHERE run_id=? AND group_id=?',(run_id,group_id)).fetchone()
    return dict(row) if row else None


def write_record(conn,run_id,group_id,category,revision,record):
    """Never overwrite the bytes of a revision already referenced by a consumer."""
    hashed=digest(record)
    if revision!=hashed: raise ValueError('Component revision must hash its complete metadata')
    previous=conn.execute('SELECT record_hash,record_json FROM conversion_component_records WHERE run_id=? AND group_id=? AND category=? AND revision=?',
        (run_id,group_id,category,revision)).fetchone()
    if previous and (previous[0]!=hashed or digest(json.loads(previous[1]))!=hashed):
        raise ValueError('Component revision already has different metadata')
    conn.execute('INSERT OR IGNORE INTO conversion_component_records VALUES (?,?,?,?,?,?)',
        (run_id,group_id,category,revision,json.dumps(record,sort_keys=True),hashed))


def read_record(conn,run_id,group_id,category,revision):
    """Reject missing or altered immutable proof before its revision can be reused."""
    row=conn.execute('SELECT record_json,record_hash FROM conversion_component_records WHERE run_id=? AND group_id=? AND category=? AND revision=?',
        (run_id,group_id,category,revision)).fetchone()
    if row is None: raise ValueError('Component revision evidence is missing')
    data=json.loads(row[0])
    if digest(data)!=row[1] or row[1]!=revision: raise ValueError('Component revision metadata changed')
    return data


def invalidate(conn,run_id,seeds):
    """Retain old proof while marking changed components and transitive consumers stale."""
    pending=list(seeds);seen=set()
    while pending:
        key=pending.pop()
        if key in seen: continue
        seen.add(key)
        conn.execute("UPDATE conversion_component_heads SET status='stale' WHERE run_id=? AND group_id=?",(run_id,key))
        pending.extend(row[0] for row in conn.execute('SELECT consumer_group FROM conversion_component_links WHERE run_id=? AND dependency_group=?',(run_id,key)))
    # Final unit acceptance is revision-bound too; unaffected unit siblings keep their receipts.
    if seen and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='behavior_snapshots'").fetchone():
        rows=conn.execute("""SELECT c.identity,c.data_json,v.data_json AS verification_json FROM behavior_snapshots c
            JOIN behavior_snapshots v ON v.run_id=c.run_id AND v.identity=c.identity AND v.category='unit_verification'
            WHERE c.run_id=? AND c.category='unit_components' AND v.status='accepted'""",(run_id,)).fetchall()
        for row in rows:
            if not seen.intersection(json.loads(row['data_json']).get('heads',{})):
                continue
            data=json.loads(row['verification_json'])
            data.update(status='verification_incomplete',error='Required component revision was invalidated')
            conn.execute("UPDATE behavior_snapshots SET status='verification_incomplete',fingerprint=?,data_json=?,error=? WHERE run_id=? AND category='unit_verification' AND identity=?",
                (digest(data),json.dumps(data),data['error'],run_id,row['identity']))
    return seen


def consumers(conn,run_id,group_id):
    """List direct consumers for conservative transitive invalidation."""
    return [row[0] for row in conn.execute('SELECT consumer_group FROM conversion_component_links WHERE run_id=? AND dependency_group=?',(run_id,group_id))]
