"""Read one explicit saved candidate without regenerating or replacing its Java source."""
import hashlib
import json
import sqlite3
from pathlib import Path
from models.native_unit_bundle import NativeUnitBundle
from runtime.managed_conversion_response import _remove_response_fence
from runtime.behavior_conversion.response_json import clean_structural_escapes


def read_candidate(database,attempt,unit):
    """Require unambiguous saved unit/revision evidence; open the original attempt database read-only."""
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as conn:
        rows=conn.execute('SELECT request_json,response FROM behavior_attempts WHERE category=? AND identity=? AND attempt=?',
            ('thin_path_experiment',unit['unit_id'],attempt)).fetchall()
    if len(rows)!=1:raise ValueError('Replay needs exactly one saved attempt for this unit')
    request=json.loads(rows[0][0]);selected=request.get('selected_unit',{})
    if selected.get('fingerprint')!=unit['fingerprint'] or request.get('sources')!=unit['sources']:
        raise ValueError('Saved candidate source/configuration revision differs from the selected unit')
    bundle=NativeUnitBundle.model_validate_json(clean_structural_escapes(_remove_response_fence(rows[0][1] or '')))
    files={file.path:hashlib.sha256(file.content.encode('utf-8')).hexdigest() for file in bundle.files}
    return bundle,dict(database=str(Path(database).resolve()),attempt=attempt,unit_id=unit['unit_id'],
        response_hash=hashlib.sha256(rows[0][1].encode('utf-8')).hexdigest(),source_hashes=files,
        generation_performed=False)
