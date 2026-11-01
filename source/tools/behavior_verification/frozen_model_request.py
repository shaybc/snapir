"""Verify the retained initial implementation request before a one-variable model comparison."""
import json
import sqlite3
from agents.behavior_conversion.staged_pipeline import code_instruction
from runtime.behavior_conversion.response_json import JSON_INSTRUCTION
from tools.component_inventory_tools.identity import stable_id

SETTINGS=('java_version','java_home','model_name','model_provider','model_base_url','model_timeout_seconds','max_model_attempts',
    'maven_settings_path','maven_local_repository','approved_maven_repository_urls','allowed_ibm_artifacts','allowed_ibm_classes','behavior_context_chars')


def verify_request(profile,instruction,request,fingerprint):
    """Require the original generator fingerprint, including its instruction and complete evidence."""
    actual=stable_id('staged_implementation',instruction,request,{name:getattr(profile,name) for name in SETTINGS},'behavior-v1')
    if actual!=fingerprint:raise ValueError('Saved prompt/request fingerprint cannot be reproduced; do not run an uncontrolled comparison')


def read_request(directory,profile,name):
    """Read the first returned Lite candidate, excluding provider-only failures and corrections."""
    conn=sqlite3.connect((directory/'trials.db').as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
    try:
        rows=conn.execute("SELECT * FROM behavior_attempts WHERE category='staged_implementation' AND response IS NOT NULL ORDER BY created_at,attempt").fetchall()
        row=next(row for row in rows if json.loads(row['request_json']).get('selected_unit',{}).get('logical_id')==name)
        request=json.loads(row['request_json'])
        if 'previous_model_response' in request or 'correction_feedback' in request:raise ValueError('Comparison requires an initial request, not a correction')
        instruction=code_instruction(request)+'\n'+JSON_INSTRUCTION
        verify_request(profile,instruction,request,row['fingerprint'])
        return dict(request=request,instruction=instruction,payload=json.dumps(request,ensure_ascii=False),
            fingerprint=row['fingerprint'],response=row['response'],error=row['error'],identity=row['identity'],attempt=row['attempt'])
    finally:conn.close()
