"""Durable item proofs and task-wide budgets; splitting never creates new allowances."""
import json
from contextlib import contextmanager
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools._json import utc_now


def initialize(conn):
    """Add independent mapping progress without modifying historical stage records."""
    for sql in (
        'CREATE TABLE IF NOT EXISTS metadata_checklist_tasks (run_id TEXT,task_id TEXT,ids_json TEXT,limits_json TEXT,calls INTEGER DEFAULT 0,transports INTEGER DEFAULT 0,PRIMARY KEY(run_id,task_id))',
        'CREATE TABLE IF NOT EXISTS metadata_checklist_items (run_id TEXT,task_id TEXT,item_id TEXT,attempts INTEGER DEFAULT 0,proof TEXT,status TEXT,data_json TEXT,data_hash TEXT,PRIMARY KEY(run_id,task_id,item_id))',
        'CREATE TABLE IF NOT EXISTS metadata_checklist_batches (run_id TEXT,task_id TEXT,batch_id TEXT,parent_id TEXT,data_json TEXT,status TEXT,errors_json TEXT,PRIMARY KEY(run_id,task_id,batch_id))',
        'CREATE TABLE IF NOT EXISTS metadata_checklist_attempts (run_id TEXT,task_id TEXT,call_id INTEGER,transport INTEGER,request_json TEXT,response TEXT,error TEXT,created_at TEXT,PRIMARY KEY(run_id,task_id,call_id,transport))'):
        conn.execute(sql)
    conn.commit()


@contextmanager
def transaction(conn):
    conn.execute('SAVEPOINT checklist_budget')
    try:yield
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT checklist_budget');conn.execute('RELEASE SAVEPOINT checklist_budget');raise
    conn.execute('RELEASE SAVEPOINT checklist_budget');conn.commit()


def open_task(conn,run,task,ids,limits):
    """Freeze total allowances on first execution; resume cannot replenish them."""
    initialize(conn)
    row=conn.execute('SELECT ids_json,limits_json FROM metadata_checklist_tasks WHERE run_id=? AND task_id=?',(run,task)).fetchone()
    if row:
        if json.loads(row[0])!=sorted(ids):raise ValueError('Mapping task checklist changed without a new source revision')
        return json.loads(row[1])
    with transaction(conn):
        conn.execute('INSERT INTO metadata_checklist_tasks(run_id,task_id,ids_json,limits_json) VALUES(?,?,?,?)',(run,task,json.dumps(sorted(ids)),json.dumps(limits)))
        conn.executemany('INSERT INTO metadata_checklist_items(run_id,task_id,item_id,status) VALUES(?,?,?,?)',[(run,task,key,'pending') for key in sorted(ids)])
    return limits


def accepted(conn,run,task,proof):
    """Only intact mappings for current source/code/evidence/policy can be reused."""
    result={}
    for key,stored,data,digest in conn.execute("SELECT item_id,proof,data_json,data_hash FROM metadata_checklist_items WHERE run_id=? AND task_id=? AND status='mapped'",(run,task)):
        if stable_id(json.loads(data))!=digest:raise ValueError('Checklist mapping integrity failed: '+key)
        if stored==proof:result[key]=json.loads(data)
    return result


def reserve_call(conn,run,task,ids,limits):
    """Count one logical request and each assigned item's attempt atomically."""
    with transaction(conn):
        changed=conn.execute('UPDATE metadata_checklist_tasks SET calls=calls+1 WHERE run_id=? AND task_id=? AND calls<?',(run,task,limits['calls']))
        if changed.rowcount!=1:raise ValueError('Checklist total logical-call budget exhausted')
        for key in ids:
            changed=conn.execute('UPDATE metadata_checklist_items SET attempts=attempts+1 WHERE run_id=? AND task_id=? AND item_id=? AND attempts<?',(run,task,key,limits['item_attempts']))
            if changed.rowcount!=1:raise ValueError('Checklist item attempt budget exhausted: '+key)
        return conn.execute('SELECT calls FROM metadata_checklist_tasks WHERE run_id=? AND task_id=?',(run,task)).fetchone()[0]


def reserve_transport(conn,run,task,call,number,request,limits):
    """Reserve before any provider request, including a timed-out transport retry."""
    with transaction(conn):
        changed=conn.execute('UPDATE metadata_checklist_tasks SET transports=transports+1 WHERE run_id=? AND task_id=? AND transports<?',(run,task,limits['transports']))
        if changed.rowcount!=1:raise ValueError('Checklist total transport budget exhausted')
        conn.execute('INSERT INTO metadata_checklist_attempts VALUES(?,?,?,?,?,?,?,?)',(run,task,call,number,json.dumps(request),None,None,utc_now()))


def finish_transport(conn,run,task,call,number,response=None,error=None):
    conn.execute('UPDATE metadata_checklist_attempts SET response=?,error=? WHERE run_id=? AND task_id=? AND call_id=? AND transport=?',
        (response,str(error) if error else None,run,task,call,number));conn.commit()


def save_items(conn,run,task,proof,values):
    """Independent successes remain traceability records, never unit acceptance."""
    with transaction(conn):
        for key,value in values.items():
            row=conn.execute('SELECT proof,status,data_hash FROM metadata_checklist_items WHERE run_id=? AND task_id=? AND item_id=?',(run,task,key)).fetchone()
            if row is None:raise ValueError('Cannot save unassigned checklist ID: '+key)
            if row[0]==proof and row[1]=='mapped' and row[2]!=stable_id(value):raise ValueError('Cannot overwrite an accepted sibling mapping')
            conn.execute("UPDATE metadata_checklist_items SET proof=?,status='mapped',data_json=?,data_hash=? WHERE run_id=? AND task_id=? AND item_id=?",(proof,json.dumps(value),stable_id(value),run,task,key))


def batch(conn,run,task,batch_id,parent,data,status='pending',errors=()):
    conn.execute('INSERT INTO metadata_checklist_batches VALUES(?,?,?,?,?,?,?) ON CONFLICT(run_id,task_id,batch_id) DO UPDATE SET data_json=excluded.data_json,status=excluded.status,errors_json=excluded.errors_json',
        (run,task,batch_id,parent,json.dumps(data),status,json.dumps(errors)));conn.commit()


def previous_errors(conn,run,task,batch_id):
    row=conn.execute('SELECT errors_json,data_json FROM metadata_checklist_batches WHERE run_id=? AND task_id=? AND batch_id=?',(run,task,batch_id)).fetchone()
    return (json.loads(row[0]),json.loads(row[1])) if row else ([],{})


def split_children(conn,run,task,batch_id):
    row=conn.execute('SELECT status FROM metadata_checklist_batches WHERE run_id=? AND task_id=? AND batch_id=?',(run,task,batch_id)).fetchone()
    if row and row[0]=='split':
        return [json.loads(r[0]) for r in conn.execute('SELECT data_json FROM metadata_checklist_batches WHERE run_id=? AND task_id=? AND parent_id=? ORDER BY batch_id',(run,task,batch_id))]
    return None


def mark_items(conn,run,task,ids,status):
    """Record unfinished-item classification without erasing proof/data or attempts."""
    with transaction(conn):
        conn.executemany('UPDATE metadata_checklist_items SET status=? WHERE run_id=? AND task_id=? AND item_id=?',
            [(status,run,task,key) for key in ids])
