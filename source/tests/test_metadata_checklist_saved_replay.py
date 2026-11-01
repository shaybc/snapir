"""Read-only replay of a saved failure; fixture citations prove mechanics, not equivalence."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.native_implementation import NativeImplementation
from models.native_unit_bundle import NativeSourceFile
from models.native_component_bundle import NativeComponentBundle
from models.staged_metadata import metadata_schema
from runtime.behavior_conversion.metadata_checklist import map_checklist
from runtime.behavior_conversion.metadata_semantics import semantic_request
from runtime.behavior_conversion.native_metadata import inspect_native
from runtime.behavior_conversion.request_context import encode_request
from runtime.java_toolchain import java_scope
from agents.behavior_conversion.metadata_checklist import SEMANTICS
from tests.runtime.test_behavior_conversion import state


def test_saved_168_item_request_is_bounded_and_repairs_only_unfinished_ids(tmp_path):
    db=Path(__file__).resolve().parents[2]/'outputs/single-operation-full-current-20261031-052006/single-get-client-links/state/migration.db'
    if not db.exists():pytest.skip('Optional historical read-only replay fixture is not present')
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as historical:
        row=historical.execute("SELECT request_json FROM staged_conversion_attempts WHERE identity LIKE '%9769%' AND stage='metadata' ORDER BY updated_at DESC LIMIT 1").fetchone()
    assert row,'Saved 168-item failure must exist'
    payload=json.loads(row[0]);assert len(payload['parser_checklist'])==168
    production=NativeImplementation(files=payload['production_files'])
    prerequisites={p:t for component in payload['prerequisite_components'] for p,t in component['sources'].items()}
    owned={f.path for f in production.files}
    files=[*production.files,*[NativeSourceFile(path=p,content=t) for p,t in prerequisites.items() if p not in owned]]
    profile=PipelineConfiguration(java_version=25,model_provider='mock')
    with java_scope(profile):inventory=inspect_native(files,original_sources=payload['sources'])
    semantic=semantic_request(payload,production,inventory)
    schema=metadata_schema(NativeComponentBundle,True)
    _,semantic_text=encode_request(dict(semantic,schema=schema.model_json_schema()),SEMANTICS,84000)
    seen=[];bad=[]
    def model(prompt,text):
        req=json.loads(text);seen.append(req)
        assert len(text)+len(prompt)<=84000
        assert 1<=len(req['assigned_items'])<=15
        assert 'previous_model_response' not in req and 'parser_checklist' not in req
        native=next(e for e in req['evidence'] if e['kind']=='native')
        entries=[dict(checklist_id=i['id'],status='implemented',locations=[dict(path=native['owner'],excerpt=native['content'])]) for i in req['assigned_items']]
        if not bad:
            bad.append(entries[-1]['checklist_id']);entries[-1]['locations'][0]['excerpt']='absent-fixture-excerpt'
        if req['errors']:
            assert [i['id'] for i in req['assigned_items']]==bad
            assert {e['code'] for e in req['errors']}=={'excerpt_not_found'}
        return json.dumps(dict(task_revision=req['task_revision'],production_revision=req['production_revision'],batch_id=req['batch_id'],entries=entries))
    conn,config=state()
    tasks=SimpleNamespace(conn=conn,config=config,profile=profile,identity=payload['group_id'],revision=payload['input_revision'],
        model_call=model,validator=SimpleNamespace(stage_prerequisites=prerequisites),fresh=lambda:None)
    try:
        result=map_checklist(tasks,payload,production,inventory)
        assert len(result['checklist_implementations'])==168
        assert sum(len(r['assigned_items']) for r in seen)==169
        tasks.model_call=lambda *a:pytest.fail('Unchanged replay must retain all current mappings')
        assert map_checklist(tasks,payload,production,inventory)==result
        report=dict(assigned_items=168,fixture_mapped_items=168,requests=len(seen),largest_batch=max(len(r['assigned_items']) for r in seen),
            request_characters=[len(json.dumps(r,ensure_ascii=False)) for r in seen],semantic_request_characters=len(semantic_text),
            traceability_fixture_only=True,behavioral_acceptance=False,provider_calls=0)
        (tmp_path/'metadata-2-saved-replay.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Saved replay measurements: '+json.dumps(report))
    finally:conn.close()
