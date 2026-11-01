"""No-provider fixtures exercise partial retention, evidence expansion and all stage roles."""
import json
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.native_implementation import NativeImplementation
from runtime.behavior_conversion.metadata_checklist import map_checklist
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tests.runtime.test_behavior_conversion import state
from test_metadata_checklist import items,answer,ORIGINAL,CODE,PATH


def setup(model,**settings):
    conn,config=state();profile=PipelineConfiguration(metadata_checklist_batch_items=2,**settings)
    tasks=SimpleNamespace(conn=conn,config=config,profile=profile,identity='fixture',revision='source-revision',
        model_call=model,validator=SimpleNamespace(stage_prerequisites={}),fresh=lambda:None)
    payload=dict(sources=[dict(identity='original',content=ORIGINAL)],parser_checklist=items())
    return tasks,payload,NativeImplementation(files=[dict(path=PATH,content=CODE)])


def reply(req,entries=None,**other):
    return json.dumps(dict(task_revision=req['task_revision'],production_revision=req['production_revision'],batch_id=req['batch_id'],
        entries=entries if entries is not None else [answer(i['id']) for i in req['assigned_items']],**other))


def test_partial_valid_items_are_retained_repaired_alone_and_resume_without_calls():
    seen=[]
    def model(prompt,text):
        req=json.loads(text);seen.append(req)
        if len(seen)==1:return reply(req,[answer(req['assigned_items'][0]['id']),answer(req['assigned_items'][1]['id'],'wrong')])
        if req['errors']:
            assert all(e['code']=='excerpt_not_found' for e in req['errors'])
            assert len(req['assigned_items'])==1
        return reply(req)
    tasks,payload,production=setup(model)
    try:
        mapped=map_checklist(tasks,payload,production,{})
        assert len(mapped['checklist_implementations'])==6
        assert len(seen)==4
        tasks.model_call=lambda *a:pytest.fail('Unchanged resume must not call model')
        assert map_checklist(tasks,payload,production,{})==mapped
        assert tasks.conn.execute('SELECT count(*) FROM metadata_checklist_attempts').fetchone()[0]==4
    finally:tasks.conn.close()


def test_timeout_splits_share_parent_item_and_transport_budgets():
    seen=[]
    def model(prompt,text):
        req=json.loads(text);seen.append(req)
        if len(seen)<=2:raise TimeoutError('timeout')
        return reply(req)
    tasks,payload,production=setup(model,max_agent_task_retries=2)
    payload['parser_checklist']=items(2)
    try:
        assert len(map_checklist(tasks,payload,production,{})['checklist_implementations'])==2
        assert [len(r['assigned_items']) for r in seen]==[2,2,1,1]
        assert tuple(tasks.conn.execute('SELECT calls,transports FROM metadata_checklist_tasks').fetchone())==(3,4)
        assert all(r[0]==2 for r in tasks.conn.execute('SELECT attempts FROM metadata_checklist_items'))
    finally:tasks.conn.close()


def test_transport_exhaustion_is_incomplete_and_cannot_be_replenished():
    tasks,payload,production=setup(lambda *a:(_ for _ in ()).throw(TimeoutError('timeout')),metadata_checklist_max_transport_calls=1)
    try:
        for _ in range(2):
            with pytest.raises(VerificationIncomplete,match='budget'):map_checklist(tasks,payload,production,{})
        assert tasks.conn.execute('SELECT count(*) FROM metadata_checklist_attempts').fetchone()[0]==1
    finally:tasks.conn.close()


def test_exact_supporting_evidence_expands_without_recreating_completed_mappings():
    seen=[]
    def model(prompt,text):
        req=json.loads(text);seen.append(req)
        supporting=next(e for e in req['evidence_catalog'] if e['owner']=='support')
        if len(seen)==1:return reply(req,[],evidence_requests=[supporting['ranges'][0]['evidence_id']])
        assert any(e['owner']=='support' for e in req['evidence'])
        return reply(req)
    tasks,payload,production=setup(model);payload['parser_checklist']=items(1)
    payload['sources'].append(dict(identity='support',content='package original; public class Support { public int helper(){return 1;} }'))
    try:
        assert len(map_checklist(tasks,payload,production,{})['checklist_implementations'])==1
        assert len(seen)==2
    finally:tasks.conn.close()


def test_unresolved_model_concern_never_becomes_automatic_production_rewrite():
    def model(prompt,text):
        req=json.loads(text)
        return reply(req,[dict(checklist_id=i['id'],status='unresolved',question='Cannot find this implementation') for i in req['assigned_items']])
    tasks,payload,production=setup(model,max_agent_task_retries=1);payload['parser_checklist']=items(1)
    try:
        with pytest.raises(VerificationIncomplete,match='implementation_concern'):map_checklist(tasks,payload,production,{})
        row=tasks.conn.execute('SELECT errors_json FROM metadata_checklist_batches WHERE status=\'needs_correction\'').fetchone()
        assert 'implementation_concern' in row[0]
        assert tasks.conn.execute('SELECT calls FROM metadata_checklist_tasks').fetchone()[0]==1
        assert tasks.conn.execute('SELECT status FROM metadata_checklist_items').fetchone()[0]=='implementation_concern'
        assert not tasks.conn.execute("SELECT name FROM sqlite_master WHERE name='staged_conversion_attempts'").fetchone()
    finally:tasks.conn.close()


@pytest.mark.parametrize('kind',['basic_component','configured_step','format_subtree'])
def test_full_component_roles_derive_identity_and_apis_before_batched_mapping(monkeypatch,kind):
    from test_staged_pipeline import request,Validator,PKG,PATH as target,CODE as code,TEST_PATH,TEST
    from models.native_component_bundle import NativeComponentBundle
    from models.native_test_bundle import NativeTestBundle
    from runtime.behavior_conversion.generation import generate
    from runtime.java_toolchain import java_scope
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    conn,config=state();payload=request(kind);payload['sources']=[dict(identity='original',content=ORIGINAL)]
    payload['parser_checklist']=items(3);calls=[];validator=Validator()
    def model(prompt,text):
        req=json.loads(text);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return NativeImplementation(files=[dict(path=target,content=code)]).model_dump_json()
        if title=='NativeComponentSemantics':
            assert 'parser_checklist' not in req and 'previous_response' not in req
            assert 'evidence_ids' not in req['schema']['properties']
            api=next(a for a in req['parsed_apis'] if a['type_name']==PKG+'.Formatter')
            return json.dumps(dict(contracts={'component':dict(api_types=[api['type_name']],api_members={api['type_name']:[api['members'][0]['member_id']]})}))
        if title=='MetadataChecklistBatch':
            assert len(req['assigned_items'])<=2 and 'contracts' not in req
            return reply(req,[answer(i['id'],'return value;',target) for i in req['assigned_items']])
        assert title=='NativeTestBundle'
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)],coverage={k:[TEST_PATH] for k in req['requirements']}).model_dump_json()
    try:
        with java_scope(PipelineConfiguration(java_version=25)):
            bundle,_=generate(conn,config,PipelineConfiguration(java_version=25,model_provider='mock',metadata_checklist_batch_items=2),
                'component_generation','unit','unused',payload,NativeComponentBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeComponentSemantics','MetadataChecklistBatch','MetadataChecklistBatch','NativeTestBundle']
        assert set(bundle.checklist_implementations)=={i['id'] for i in payload['parser_checklist']}
        contract=bundle.contracts['component']
        assert contract.component_id=='component' and contract.evidence_ids==['source']
        assert len(contract.apis)==1 and len(contract.apis[0].method_signatures)==1
        assert validator.compiles==validator.checks==1
    finally:conn.close()


def test_changed_production_invalidates_mappings_without_resetting_item_budgets():
    calls=[]
    def model(prompt,text):
        req=json.loads(text);calls.append(req);return reply(req)
    tasks,payload,production=setup(model,max_agent_task_retries=2)
    payload['parser_checklist']=items(2)
    try:
        map_checklist(tasks,payload,production,{})
        production.files[0].content=CODE.replace('return 0;','return 0; /* changed production */')
        map_checklist(tasks,payload,production,{})
        assert len(calls)==2 and calls[0]['production_revision']!=calls[1]['production_revision']
        assert calls[0]['task_revision']==calls[1]['task_revision']
        assert all(row[0]==2 for row in tasks.conn.execute('SELECT attempts FROM metadata_checklist_items'))
    finally:tasks.conn.close()


def test_original_parser_failure_is_tooling_not_model_implementation_repair(monkeypatch):
    from test_staged_pipeline import request,Validator,PATH as target,CODE as code
    from models.native_component_bundle import NativeComponentBundle
    from runtime.behavior_conversion.generation import generate
    from runtime.java_toolchain import java_scope
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    conn,config=state();payload=request();payload['parser_checklist']=items(1);calls=[]
    def model(prompt,text):
        calls.append(json.loads(text)['schema']['title'])
        return NativeImplementation(files=[dict(path=target,content=code)]).model_dump_json()
    try:
        with java_scope(PipelineConfiguration(java_version=25)):
            with pytest.raises(VerificationIncomplete,match='metadata_original_parser'):
                generate(conn,config,PipelineConfiguration(java_version=25,model_provider='mock'),
                    'component_generation','unit','unused',payload,NativeComponentBundle,validator=Validator(),model_call=model)
        assert calls==['NativeImplementation']
    finally:conn.close()
