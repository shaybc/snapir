"""Copy retained stage counters and verify frozen production without relocating acceptance claims."""
import hashlib
import json
import sqlite3
from models.native_implementation import NativeImplementation
from tools.component_inventory_tools.identity import stable_id


def load_compiled_candidate(directory):
    """Require a compiled artifact with matching saved stage and source hashes."""
    report=json.loads((directory/'model-comparison.json').read_text())
    if not report.get('production_compile',{}).get('build_passed') or report.get('unit_accepted'):
        raise ValueError('Continuation requires a compiled, not-yet-accepted candidate')
    source=directory/'comparison.db';conn=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    try:
        row=conn.execute("SELECT identity,revision,artifact_json,artifact_hash FROM staged_conversion_tasks WHERE stage='implementation' AND status='retained'").fetchone()
        if row is None:raise ValueError('No retained production implementation')
        value=NativeImplementation.model_validate_json(row[2])
        proof_row=conn.execute("SELECT artifact_json FROM staged_conversion_tasks WHERE stage='compile' AND identity=? AND revision=?",(row[0],row[1])).fetchone()
        proof=json.loads(proof_row[0]) if proof_row and proof_row[0] else {}
        content_hash=proof.get('production_hash')
        if not proof.get('validation',{}).get('build_passed') or stable_id(value.model_dump(mode='json'))!=content_hash:
            raise ValueError('Saved production artifact hash changed or compile proof is missing')
        if conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category IN ('unit','unit_verification') AND status='accepted'").fetchone()[0]:
            raise ValueError('Accepted unit evidence must remain with its owning run')
        return value,dict(identity=row[0],revision=row[1],implementation_hash=content_hash,artifact_fingerprint=row[3],database_hash=hashlib.sha256(source.read_bytes()).hexdigest())
    finally:conn.close()


def copy_stage_state(directory,target,*,database='comparison.db'):
    """Retain counters and prior attempts; later stages must revalidate before acceptance."""
    if target.exists():raise ValueError('Continuation database already exists')
    source=sqlite3.connect((directory/database).as_uri()+'?mode=ro',uri=True)
    destination=sqlite3.connect(target)
    try:source.backup(destination)
    finally:source.close();destination.close()
