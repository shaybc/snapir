"""Compiled continuation binds source bytes to compile proof and retains stage counters."""
import json
import sqlite3
import pytest
from models.native_implementation import NativeImplementation
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools import staged_conversion_state as state
from tools.state_store_tools.behavior_units import initialize
from tools.behavior_verification.frozen_trial_state import load_compiled_candidate,copy_stage_state


def saved(tmp_path):
    folder=tmp_path/'saved';folder.mkdir()
    value=NativeImplementation(files=[{'path':'src/main/java/Work.java','content':'public class Work {}'}])
    (folder/'model-comparison.json').write_text(json.dumps({'production_compile':{'build_passed':True},'unit_accepted':False}))
    conn=sqlite3.connect(folder/'comparison.db');initialize(conn)
    state.retain(conn,'run','unit','rev','implementation',value.model_dump(mode='json'),'request-fingerprint-not-content-hash')
    state.retain(conn,'run','unit','rev','compile',{'production_hash':stable_id(value.model_dump(mode='json')),'validation':{'build_passed':True}},'compile-hash')
    state.reserve(conn,'run','unit','rev','semantic_metadata',4,{})
    state.finish(conn,'run','unit','rev','semantic_metadata',1,error='replay stopped before provider')
    conn.close();return folder,value


def test_loader_uses_content_proof_not_request_fingerprint(tmp_path):
    folder,value=saved(tmp_path);loaded,proof=load_compiled_candidate(folder)
    assert loaded==value and proof['implementation_hash']==stable_id(value.model_dump(mode='json'))
    assert proof['artifact_fingerprint']=='request-fingerprint-not-content-hash'
    copy_stage_state(folder,tmp_path/'continued.db')
    conn=sqlite3.connect(tmp_path/'continued.db')
    try:assert state.reserve(conn,'run','unit','rev','semantic_metadata',4,{})==2
    finally:conn.close()


def test_loader_rejects_code_changed_after_compile(tmp_path):
    folder,value=saved(tmp_path);value.files[0].content+=' changed'
    conn=sqlite3.connect(folder/'comparison.db')
    conn.execute("UPDATE staged_conversion_tasks SET artifact_json=? WHERE stage='implementation'",(value.model_dump_json(),));conn.commit();conn.close()
    with pytest.raises(ValueError,match='artifact hash changed'):load_compiled_candidate(folder)
