"""Persist side-road stage budgets and verified baselines independently of request fingerprints."""
import json
from tools.state_store_tools._json import utc_now


def load(conn, run_id, identity, revision):
    """Create/read one durable record per parent unit and evidence revision."""
    conn.execute('''CREATE TABLE IF NOT EXISTS side_road_conversions (
        run_id TEXT, identity TEXT, revision TEXT, baseline_attempts INTEGER NOT NULL DEFAULT 0,
        simplify_attempts INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'started',
        baseline_json TEXT, receipt_json TEXT, error TEXT, updated_at TEXT,
        PRIMARY KEY(run_id,identity,revision))''')
    conn.execute('INSERT OR IGNORE INTO side_road_conversions(run_id,identity,revision,updated_at) VALUES(?,?,?,?)',
                 (run_id, identity, revision, utc_now()))
    conn.commit()
    cursor = conn.execute('SELECT * FROM side_road_conversions WHERE run_id=? AND identity=? AND revision=?',
                          (run_id, identity, revision))
    return dict(zip([column[0] for column in cursor.description], cursor.fetchone()))


def reserve_attempt(conn, run_id, identity, revision, stage, maximum):
    """Consume before model execution, atomically; interrupted calls still count."""
    if stage not in {'baseline','simplify'}:
        raise ValueError('Unknown side-road stage')
    field = stage+'_attempts'
    cursor = conn.execute(f'UPDATE side_road_conversions SET {field}={field}+1,updated_at=? '
        f'WHERE run_id=? AND identity=? AND revision=? AND {field}<?',
        (utc_now(),run_id,identity,revision,maximum))
    conn.commit()
    if cursor.rowcount != 1:
        raise ValueError('Side-road '+stage+' attempt budget exhausted')


def record(conn, run_id, identity, revision, status, *, baseline=None, receipt=None, error=None):
    """Retain the verified baseline even when simplification fails."""
    conn.execute('''UPDATE side_road_conversions SET status=?,
        baseline_json=COALESCE(?,baseline_json),receipt_json=COALESCE(?,receipt_json),error=?,updated_at=?
        WHERE run_id=? AND identity=? AND revision=?''',
        (status,baseline.model_dump_json() if baseline is not None else None,
         json.dumps(receipt) if receipt is not None else None,error,utc_now(),run_id,identity,revision))
    conn.commit()
