"""Actual limits and prerequisite failures remain distinct and cannot silently approve incomplete work."""
from types import SimpleNamespace
import pytest
from comparator import state, interaction_review
from comparator.state import Tasks
from comparator.models import Incomplete
from comparator.review_limits import LimitReached
from comparator.review_issues import ReviewIssues
from comparator.workflow import run
from comparator.reporting import finish
from support import settings, sources, Model


@pytest.mark.parametrize('limit',['max_model_calls','max_run_seconds','request_character_limit','max_model_attempts','max_evidence_rounds'])
def test_task_errors_identify_the_exact_exhausted_limit(tmp_path,monkeypatch,limit):
    timer=SimpleNamespace(now=0)
    monkeypatch.setattr(state,'time',SimpleNamespace(monotonic=lambda:timer.now))
    config=settings();config['implementation_hash']='test'
    if limit in {'max_model_attempts','max_evidence_rounds'}: config[limit]=2
    if limit=='request_character_limit': config[limit]=1
    def ask(*args):
        return 'invalid JSON' if limit=='max_model_attempts' else '{"need_evidence":["body"]}'
    tasks=Tasks(config,tmp_path/'cache',{'body':dict(source='return value;')},ask=ask)
    if limit=='max_model_calls': tasks.calls=config[limit]
    if limit=='max_run_seconds': timer.now=config[limit]+1
    with pytest.raises(LimitReached) as failure:
        tasks.call('inventory','prompt',{},lambda value:None,{'body'})
    assert failure.value.setting==limit
    assert tasks.budget_summary()[limit]['exhausted'] is True
    assert limit in str(failure.value)


@pytest.mark.parametrize('limit',['max_model_calls','max_run_seconds'])
def test_validated_cached_task_replays_at_a_global_limit(tmp_path,monkeypatch,limit):
    timer=SimpleNamespace(now=0)
    monkeypatch.setattr(state,'time',SimpleNamespace(monotonic=lambda:timer.now))
    config=settings();config['implementation_hash']='test'
    tasks=Tasks(config,tmp_path/'cache',{},ask=lambda *args:'{"ok":true}')
    tasks.call('interaction','prompt',{},lambda value:None,set())
    if limit=='max_model_calls': tasks.calls=config[limit]
    else: timer.now=config[limit]+1
    tasks.ask=lambda *args:pytest.fail('Repeated cached model request')
    assert tasks.call('interaction','prompt',{},lambda value:None,set())==dict(ok=True)
    assert not tasks.budget_summary()[limit]['exhausted']


def fixtures(count=3):
    behaviors=[dict(id='b'+str(i),source='member',state_fields=[]) for i in range(count)]
    pair=dict(original_class='old.Old',generated_class='native.New')
    tasks=SimpleNamespace(settings=dict(max_interaction_pairs=1),calls=0,cached_receipts=set())
    return tasks,behaviors,pair


def test_unmapped_pairs_never_spend_interaction_allowance_or_repeat_warnings(monkeypatch):
    tasks,behaviors,pair=fixtures();issues=ReviewIssues();results=[];seen=[]
    cause=issues.add('No counterpart for b0',category='unmapped_behavior',reference='b0')
    def compare(*args):
        seen.append([value['id'] for value in args[2]]);tasks.calls+=1
        return dict(verdict='consistent')
    monkeypatch.setattr(interaction_review,'compare',compare)
    stats=interaction_review.review(tasks,None,behaviors,{'b0':[],'b1':['g1'],'b2':['g2']},{'b0':cause},
        dict(edges={}),{},dict(uncertainties=[]),pair,issues,results)
    assert seen==[['b1','b2']] and stats['reviewed']==1 and not stats['limit_exhausted']
    assert stats['unmapped_behaviors']==1 and len(issues.summary())==1
    assert issues.summary()[0]['blocked_behaviors']==1
    assert 'budget' not in issues.summary()[0]['suggested_action'].lower()


def test_only_actual_eligible_pair_attempts_can_hit_pair_limit(monkeypatch):
    tasks,behaviors,pair=fixtures();issues=ReviewIssues();results=[]
    monkeypatch.setattr(interaction_review,'compare',lambda *args:dict(verdict='consistent'))
    stats=interaction_review.review(tasks,None,behaviors,{b['id']:['g'] for b in behaviors},{},
        dict(edges={}),{},dict(uncertainties=[]),pair,issues,results)
    assert stats['attempted']==1 and stats['limit_exhausted']
    assert len(issues.summary())==1 and issues.summary()[0]['limit']['setting']=='max_interaction_pairs'


def test_cached_interaction_is_replayed_even_when_global_calls_are_at_limit(monkeypatch):
    tasks,behaviors,pair=fixtures(2);tasks.calls=200;issues=ReviewIssues()
    monkeypatch.setattr(interaction_review,'compare',lambda *args:dict(verdict='consistent'))
    stats=interaction_review.review(tasks,None,behaviors,{b['id']:['g'] for b in behaviors},{},
        dict(edges={}),{},dict(uncertainties=[]),pair,issues,[])
    assert stats['reviewed']==1 and not issues.summary()


def test_declined_model_call_does_not_consume_pair_allowance(monkeypatch):
    tasks,behaviors,pair=fixtures();issues=ReviewIssues()
    def compare(*args): raise LimitReached('max_model_calls',200,200,'interaction')
    monkeypatch.setattr(interaction_review,'compare',compare)
    stats=interaction_review.review(tasks,None,behaviors,{b['id']:['g'] for b in behaviors},{},
        dict(edges={}),{},dict(uncertainties=[]),pair,issues,[])
    assert stats['attempted']==0 and not stats['limit_exhausted'] and stats['deferred']
    assert issues.summary()[0]['limit']['setting']=='max_model_calls'


def test_budget_report_groups_root_causes_and_can_resume_from_cached_work(tmp_path):
    config=settings();config['max_model_calls']=1;request=sources(tmp_path);model=Model()
    first=run(config,request,tmp_path/'reports',ask=model)
    assert first['decision']=='inconclusive'
    assert first['budgets']['max_model_calls']==dict(limit=1,used=1,exhausted=True)
    limits=[item for item in first['root_causes'] if item.get('limit',{}).get('setting')=='max_model_calls']
    assert len(limits)==1 and limits[0]['occurrences']>=1
    assert not any('Interaction has an unmapped behavior' in item['message'] for item in first['remarks'])
    resumed=run(settings(),request,tmp_path/'reports',ask=model)
    assert resumed['decision']=='consistent_in_review' and model.calls.count('boundary')==1
    assert resumed['cache']['reused_receipts']>=1


def test_uncertainties_are_grouped_with_evidence_and_do_not_get_generic_budget_advice(tmp_path):
    issues=ReviewIssues()
    for member in ('first','second'):
        issues.add('Missing versus null input is unresolved.',category='boundary_uncertainty',stage='boundary',reference=member)
        issues.add('Context write needs source tracing.',category='generated_coverage',stage='coverage',source=member,side='generated')
    unresolved=[dict(verdict='inconclusive',explanation='Caller contract is unclear.',suggested_action='Trace the caller.',
        original_evidence=[member],generated_evidence=['generated-'+member]) for member in ('first','second')]
    roots=issues.summary()
    report=finish(dict(input_hash='fixture',files={}),[],unresolved,[item['message'] for item in roots],0,[],tmp_path,root_causes=roots)
    assert report['decision']=='inconclusive' and len(report['remarks'])==3
    assert len(report['root_causes'])==2 and all(item['occurrences']==2 for item in roots)
    assert all('budget' not in item['suggested_action'].lower() for item in report['remarks'])
    behavior=next(item for item in report['remarks'] if item['category']=='behavior_uncertainty')
    assert behavior['original_evidence']==['first','second'] and behavior['occurrences']==2
    generated=next(item for item in report['remarks'] if item['category']=='generated_coverage')
    assert generated['generated_evidence']==['first','second']
