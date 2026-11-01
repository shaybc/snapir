"""Carry provider-only trial counters forward without changing historical trial databases."""
import hashlib
import json
import sqlite3


def enforce_inherited_budget(conn,run_id,identity,maximum):
    """A changed stage revision cannot replenish this trial unit's inherited provider-call budget."""
    total=conn.execute("SELECT COALESCE(SUM(attempts),0) FROM staged_conversion_tasks WHERE run_id=? AND identity=? AND stage='implementation'",
        (run_id,identity)).fetchone()[0]
    if total<=maximum:return
    from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
    from tools.state_store_tools import staged_conversion_state as state
    error=VerificationIncomplete(dict(stage='inherited_attempt_budget',errors=['Inherited implementation attempt budget exhausted'],attempts=total,maximum=maximum))
    running=conn.execute("SELECT revision,attempts FROM staged_conversion_tasks WHERE run_id=? AND identity=? AND stage='implementation' AND status='running'",
        (run_id,identity)).fetchall()
    for revision,attempt in running:state.finish(conn,run_id,identity,revision,'implementation',attempt,error=error)
    raise error


def inherit_provider_attempts(prior,directory):
    """Copy a stopped, candidate-free bank trial ledger into a fresh trial directory."""
    from tools.behavior_verification.thin_path_request import OPERATION
    report=json.loads((prior/'acceptance-trials.json').read_text(encoding='utf-8'))
    if report.get('status')!='blocked' or report.get('operation')!=OPERATION:
        raise ValueError('Only a stopped bank acceptance trial can supply attempt counters')
    source=prior/'trials.db';destination=directory/'trials.db'
    if destination.exists():raise ValueError('Trial destination state already exists')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    original=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    try:
        if original.execute('SELECT count(*) FROM behavior_attempts WHERE response IS NOT NULL').fetchone()[0]:
            raise ValueError('Provider-only rerun cannot relocate candidate artifacts; use their owning run')
        if original.execute("SELECT count(*) FROM behavior_snapshots WHERE status='accepted'").fetchone()[0]:
            raise ValueError('Provider-only rerun cannot inherit acceptance claims')
        counters=[dict(identity=row[0],revision=row[1],stage=row[2],attempts=row[3]) for row in original.execute(
            'SELECT identity,revision,stage,attempts FROM staged_conversion_tasks WHERE attempts>0 ORDER BY identity,stage')]
        copied=sqlite3.connect(destination)
        try:original.backup(copied)
        finally:copied.close()
    finally:original.close()
    if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise ValueError('Historical trial state changed during inheritance')
    return dict(prior_trial=str(prior),prior_database_hash=before,inherited_role_counters=counters,acceptance_inherited=False)
