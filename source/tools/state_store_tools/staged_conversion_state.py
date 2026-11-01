"""Persist immutable stage artifacts and counters independent of candidate fingerprints."""
import json
from tools.state_store_tools._json import utc_now
from tools.component_inventory_tools.identity import stable_id


def initialize(conn):
    """Create private staged-task storage without changing ordinary unit acceptance tables."""
    conn.execute('''CREATE TABLE IF NOT EXISTS staged_conversion_tasks (
        run_id TEXT, identity TEXT, revision TEXT, stage TEXT, attempts INTEGER NOT NULL DEFAULT 0,
        artifact_json TEXT, artifact_hash TEXT, status TEXT NOT NULL DEFAULT 'pending',error TEXT,updated_at TEXT,
        PRIMARY KEY(run_id,identity,revision,stage))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS staged_conversion_attempts (
        run_id TEXT,identity TEXT,revision TEXT,stage TEXT,attempt INTEGER,request_json TEXT,
        response TEXT,error TEXT,updated_at TEXT,PRIMARY KEY(run_id,identity,revision,stage,attempt))''')
    conn.commit()


def read(conn,run_id,identity,revision,stage):
    """Return retained stage state, without interpreting a flag as technical acceptance."""
    initialize(conn)
    conn.execute('INSERT OR IGNORE INTO staged_conversion_tasks(run_id,identity,revision,stage,updated_at) VALUES(?,?,?,?,?)',
                 (run_id,identity,revision,stage,utc_now()))
    conn.commit()
    cursor=conn.execute('SELECT * FROM staged_conversion_tasks WHERE run_id=? AND identity=? AND revision=? AND stage=?',
                        (run_id,identity,revision,stage))
    return dict(zip([column[0] for column in cursor.description],cursor.fetchone()))


def reserve(conn,run_id,identity,revision,stage,maximum,request):
    """Reserve before each logical model call; candidate changes cannot replenish attempts."""
    read(conn,run_id,identity,revision,stage)
    cursor=conn.execute('UPDATE staged_conversion_tasks SET attempts=attempts+1,status=?,updated_at=? '
        'WHERE run_id=? AND identity=? AND revision=? AND stage=? AND attempts<?',
        ('running',utc_now(),run_id,identity,revision,stage,maximum))
    if cursor.rowcount!=1:
        conn.rollback()
        raise ValueError('Staged '+stage+' attempt budget exhausted')
    attempt=conn.execute('SELECT attempts FROM staged_conversion_tasks WHERE run_id=? AND identity=? AND revision=? AND stage=?',
                         (run_id,identity,revision,stage)).fetchone()[0]
    conn.execute('INSERT INTO staged_conversion_attempts VALUES(?,?,?,?,?,?,?,?,?)',
        (run_id,identity,revision,stage,attempt,json.dumps(request),None,None,utc_now()))
    conn.commit()
    return attempt


def invalidate_readiness(conn,run_id,identity,revision,owner):
    """Retain historical proofs but require a fresh gate after upstream work starts."""
    initialize(conn)
    stages=('implementation_ready','tests_ready') if owner in {'implementation','binding'} else ('tests_ready',)
    for stage in stages:
        conn.execute('UPDATE staged_conversion_tasks SET status=?,updated_at=? WHERE run_id=? AND identity=? AND revision=? AND stage=?',
            ('stale',utc_now(),run_id,identity,revision,stage))
    conn.commit()


def finish(conn,run_id,identity,revision,stage,attempt,*,response=None,error=None):
    """Keep request/response/error evidence for every attempt."""
    conn.execute('UPDATE staged_conversion_attempts SET response=?,error=?,updated_at=? '
        'WHERE run_id=? AND identity=? AND revision=? AND stage=? AND attempt=?',
        (response,str(error) if error else None,utc_now(),run_id,identity,revision,stage,attempt))
    conn.execute('UPDATE staged_conversion_tasks SET status=?,error=?,updated_at=? '
        'WHERE run_id=? AND identity=? AND revision=? AND stage=?',
        ('failed' if error else 'response_received',str(error) if error else None,utc_now(),run_id,identity,revision,stage))
    conn.commit()


def retain(conn,run_id,identity,revision,stage,artifact,digest):
    """Persist stage output bound to exact production/source inputs; never mark a unit accepted."""
    read(conn,run_id,identity,revision,stage)
    conn.execute('UPDATE staged_conversion_tasks SET artifact_json=?,artifact_hash=?,status=?,updated_at=? '
        'WHERE run_id=? AND identity=? AND revision=? AND stage=?',
        (json.dumps(artifact),digest,'retained',utc_now(),run_id,identity,revision,stage))
    conn.commit()


def retain_passing_tests(conn,run_id,identity,revision,tests,context,validation):
    """Keep executed passing tests independently of later comparison/acceptance failure."""
    if not validation or validation.get('build_passed') is not True or validation.get('tests_passed') is not True or validation.get('test_count',0)<=0:
        return False
    artifact=dict(tests=tests,test_hash=stable_id(tests),context=context,
                  validation=validation,recorded_at=utc_now(),accepted=False)
    retain(conn,run_id,identity,revision,'passing_tests',artifact,stable_id(artifact))
    return True


def passing_tests(conn,run_id,identity,revision,eligibility_hash):
    """Read intact tests for the same original evidence/policy, never reuse a pass receipt."""
    row=read(conn,run_id,identity,revision,'passing_tests')
    if not row['artifact_json']:return None
    artifact=json.loads(row['artifact_json'])
    if stable_id(artifact)!=row['artifact_hash'] or stable_id(artifact['tests'])!=artifact['test_hash']:
        raise ValueError('Retained passing tests failed integrity checks')
    if artifact['context']['revision']!=revision or artifact['context']['eligibility_hash']!=eligibility_hash:
        return None
    proof=artifact['validation']
    if proof.get('build_passed') is not True or proof.get('tests_passed') is not True or proof.get('test_count',0)<=0:
        raise ValueError('Retained tests have no executed passing JUnit evidence')
    return artifact


def retain_task_request(conn,run_id,identity,revision,category,request,fingerprint):
    """Preserve parent provenance without inventing an AI attempt for local bundle assembly."""
    artifact=dict(category=category,request=request,fingerprint=fingerprint)
    retain(conn,run_id,identity,revision,'task_receipt',artifact,stable_id(artifact))


def accepted_task_request(conn,run_id,category,identity,fingerprint):
    """Find the exact accepted parent request for existing route/receipt consumers."""
    initialize(conn)
    rows=conn.execute('SELECT artifact_json,artifact_hash FROM staged_conversion_tasks WHERE run_id=? AND identity=? '
        'AND stage=? AND status=? ORDER BY updated_at DESC',(run_id,identity,'task_receipt','retained')).fetchall()
    for raw,digest in rows:
        artifact=json.loads(raw)
        if stable_id(artifact)!=digest:raise ValueError('Staged parent request receipt changed')
        if artifact['category']==category and artifact['fingerprint']==fingerprint:return artifact['request']
    return None
