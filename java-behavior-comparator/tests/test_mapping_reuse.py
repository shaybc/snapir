"""Member mapping hints reduce page requests but never substitute for a behavior-specific match."""
from comparator.counterpart_mapping import locate
from comparator.state import Tasks
from support import settings


class Evidence:
    def __init__(self):
        self.chunks={'original':dict(name='format'),**{'g'+str(i):dict(signature='helper'+str(i)+'()',id='g'+str(i)) for i in range(6)}}
    def capsule(self,ids,scope): return {identity:dict(source='original behavior') for identity in ids}
    def headers(self,ids): return [self.chunks[identity] for identity in ids]
    def references(self,scope): return set(scope['ids'])


def test_member_hint_reduces_new_page_calls_and_resume_prefers_exact_cached_work(tmp_path):
    import json
    evidence=Evidence();old=dict(ids=['original']);new=dict(ids=['g'+str(i) for i in range(6)])
    config=settings();config.update(catalog_page_size=2,implementation_hash='test')
    seen=[]
    def ask(config,stage,prompt,payload,timeout):
        seen.append(payload)
        candidates=['g5'] if any(item['id']=='g5' for item in payload['generated_catalog']) else []
        return json.dumps(dict(candidates=candidates,reason='Plausible generated member for this specific behavior.'))
    tasks=Tasks(config,tmp_path/'cache',{},ask=ask)
    first=dict(id='one',source='original',description='Convert first branch')
    second=dict(id='two',source='original',description='Convert second branch')
    assert locate(tasks,evidence,first,old,new)==['g5']
    assert len(seen)==3
    assert locate(tasks,evidence,second,old,new,preferred=['g5'])==['g5']
    assert len(seen)==4 and seen[-1]['behavior']['id']=='two'
    assert tasks.mapping_reuse['preferred_matches']==1
    resumed=Tasks(config,tmp_path/'cache',{},ask=lambda *args:(_ for _ in ()).throw(AssertionError('Repeated match')))
    assert locate(resumed,evidence,first,old,new,preferred=['g0'])==['g5']
    assert resumed.calls==0


def test_hint_rejection_falls_back_to_other_catalog_members(tmp_path):
    import json
    evidence=Evidence();old=dict(ids=['original']);new=dict(ids=['g'+str(i) for i in range(6)])
    config=settings();config.update(catalog_page_size=2,implementation_hash='test')
    seen=[]
    def ask(config,stage,prompt,payload,timeout):
        seen.append(payload['catalog_page'])
        return json.dumps(dict(candidates=['g1'] if any(item['id']=='g1' for item in payload['generated_catalog']) else [],reason='Checked this behavior.'))
    tasks=Tasks(config,tmp_path/'cache',{},ask=ask)
    assert locate(tasks,evidence,dict(id='different',source='original',description='Different branch'),old,new,preferred=['g5'])==['g1']
    assert seen==['member-hint-1',1]
