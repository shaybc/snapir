"""Upgrade/resume reuses validated exact tasks while model/source changes and tampering stay isolated."""
import json
from pathlib import Path
import pytest
from comparator.models import digest, save, Incomplete
from comparator.state import Tasks
from comparator.task_cache import TaskCache, PREVIOUS_IMPLEMENTATION
from support import settings


def legacy(tmp_path,config,*,version='a'*64,model=None,response=None):
    work=tmp_path/'cache';cache=TaskCache(config,work)
    payload=dict(source='return value;',extra_evidence={})
    path=work/'tasks/test'/(cache.key('test','prompt',payload,version)+'.json')
    response=dict(ok=True) if response is None else response
    save(path,dict(response=response,response_hash=digest(response)))
    if model is not False:
        identity=model or dict(provider=config['model_provider'],name=config['model_name'],endpoint_hash=digest(config['model_base_url']))
        save(tmp_path/'runs/old/report.json',dict(implementation_hash=version,model=identity))
    return path


def validate(value):
    if value.get('ok') is not True: raise ValueError('Expected validated task result')


def test_upgrade_migrates_old_receipts_without_repeating_calls_or_overwriting_evidence(tmp_path):
    config=settings();config['implementation_hash']='current'
    old=legacy(tmp_path,config);before=old.read_bytes()
    tasks=Tasks(config,tmp_path/'cache',{},ask=lambda *args:pytest.fail('Repeated cached work'))
    assert tasks.call('test','prompt',dict(source='return value;'),validate,set())==dict(ok=True)
    assert tasks.calls==0 and len(tasks.migrated_receipts)==1
    assert old.read_bytes()==before
    config['implementation_hash']='later-reporting-change'
    resumed=Tasks(config,tmp_path/'cache',{},ask=lambda *args:pytest.fail('Repeated modern cached work'))
    resumed.call('test','prompt',dict(source='return value;'),validate,set())
    assert resumed.calls==0 and not resumed.migrated_receipts


def test_interrupted_preceding_version_without_final_report_can_resume(tmp_path):
    config=settings();config['implementation_hash']='current'
    legacy(tmp_path,config,version=PREVIOUS_IMPLEMENTATION,model=False)
    tasks=Tasks(config,tmp_path/'cache',{},ask=lambda *args:pytest.fail('Discarded interrupted cache'))
    tasks.call('test','prompt',dict(source='return value;'),validate,set())
    assert tasks.calls==0


@pytest.mark.parametrize('change',['model_name','model_base_url','model_provider','payload','prompt'])
def test_incompatible_model_or_task_data_cannot_reuse_cached_response(tmp_path,change):
    config=settings();config['implementation_hash']='current'
    legacy(tmp_path,config)
    updated=dict(config);payload=dict(source='return value;');prompt='prompt'
    if change=='payload': payload['source']='return changed;'
    elif change=='prompt': prompt='different prompt'
    else: updated[change]+='-different'
    calls=[]
    tasks=Tasks(updated,tmp_path/'cache',{},ask=lambda *args:calls.append(args) or '{"ok":true}')
    tasks.call('test',prompt,payload,validate,set())
    assert len(calls)==1 and not tasks.migrated_receipts


@pytest.mark.parametrize('tamper',[True,False])
def test_legacy_receipts_must_pass_hash_and_current_validation(tmp_path,tamper):
    config=settings();config['implementation_hash']='current'
    path=legacy(tmp_path,config,response=dict(ok=False))
    if tamper:
        value=json.loads(path.read_text());value['response_hash']='wrong';save(path,value)
    tasks=Tasks(config,tmp_path/'cache',{},ask=lambda *args:pytest.fail('Invalid cache was silently replaced'))
    with pytest.raises(Incomplete):
        tasks.call('test','prompt',dict(source='return value;'),validate,set())
    assert not tasks.migrated_receipts
