"""Bounded staged review retains uncertainty, actual evidence and resumable receipts."""
import json
from pathlib import Path
import pytest
from comparator.workflow import run
from comparator.input_catalog import catalog
from comparator.models import Incomplete
from comparator.state import Tasks
from support import sources, settings, Model, answer


def test_consistent_review_is_read_only_and_resumes_without_model_calls(tmp_path):
    request=sources(tmp_path);model=Model()
    before={str(path):path.read_bytes() for side in ('original','generated') for root in request[side]['sources'] for path in Path(root).glob('*.java')}
    report=run(settings(),request,tmp_path/'reports',ask=model)
    assert report['decision']=='consistent_in_review' and report['complete'], report
    assert {'boundary','inventory','mapping','compare','coverage'}<=set(model.calls)
    assert report['evidence_level']=='static_analysis' and 'proof' in report['limitations'][0]
    assert all(Path(path).read_bytes()==content for path,content in before.items())
    repeated=run(settings(),request,tmp_path/'reports',ask=lambda *a:pytest.fail('Unexpected repeated AI call'))
    assert repeated['model_calls']==0 and repeated['decision']=='consistent_in_review'
    assert Path(repeated['report_path']).with_name('repair-feedback.json').is_file()


def test_difference_has_two_independent_reviews_and_repair_evidence(tmp_path):
    request=sources(tmp_path,generated='package nativecode; public class New { public String format(String v){return "changed";} }')
    model=Model(difference=True)
    report=run(settings(),request,tmp_path/'reports',ask=model)
    assert report['decision']=='differences_found',report
    assert 'review_difference' in model.calls
    assert report['findings'][0]['adjudicated']
    assert report['remarks'][0]['counterexample'] and report['remarks'][0]['suggested_action']


def test_budget_exhaustion_does_not_claim_consistency_and_can_resume(tmp_path):
    request=sources(tmp_path);model=Model()
    limited=settings();limited['max_model_calls']=1
    first=run(limited,request,tmp_path/'reports',ask=model)
    assert first['decision']=='inconclusive' and not first['complete']
    resumed=run(settings(),request,tmp_path/'reports',ask=model)
    assert resumed['decision']=='consistent_in_review'
    assert model.calls.count('boundary')==1


def test_missing_source_inheritance_stays_inconclusive(tmp_path):
    request=sources(tmp_path,original='package old; public class Old extends MissingParent {public String format(String v){return v;} }')
    report=run(settings(),request,tmp_path/'reports',ask=Model())
    assert report['decision']=='inconclusive'
    assert any('MissingParent' in remark['message'] for remark in report['remarks'])


def test_unmapped_generated_behavior_and_mapping_disagreement_are_inconclusive(tmp_path):
    request=sources(tmp_path)
    def ask(config,stage,prompt,payload,timeout):
        value=answer(stage,payload,difference=True)
        if stage=='review_difference': value['verdict']='consistent'
        if stage=='coverage': value=dict(status='extra_suspected',behaviors=[],reason='Additional state mutation requires source tracing.')
        return json.dumps(value)
    report=run(settings(),request,tmp_path/'reports',ask=ask)
    assert report['decision']=='inconclusive' and not report['findings']


def test_invalid_fact_coverage_is_not_accepted(tmp_path):
    request=sources(tmp_path)
    def ask(config,stage,prompt,payload,timeout):
        value=answer(stage,payload)
        if stage=='inventory': value['behaviors'][0]['covered_facts']=[]
        return json.dumps(value)
    report=run(settings(),request,tmp_path/'reports',ask=ask)
    assert report['decision']=='inconclusive'
    assert any('Every indexed' in issue for issue in report['coverage']['unreviewed'])


def test_nonexistent_evidence_and_oversized_context_do_not_silently_pass(tmp_path):
    configured=settings();configured['implementation_hash']='test'
    tasks=Tasks(configured,tmp_path/'tasks',{},ask=lambda *args:json.dumps(dict(need_evidence=['invented'])))
    with pytest.raises(Incomplete,match='identifiers'):
        tasks.call('task','prompt',{},lambda value:None,set())
    configured['request_character_limit']=5
    with pytest.raises(Incomplete,match='no source was truncated'):
        tasks.call('task','long prompt',{},lambda value:None,set())


def test_original_and_generated_changes_invalidate_affected_work(tmp_path):
    request=sources(tmp_path);model=Model()
    first=run(settings(),request,tmp_path/'reports',ask=model)
    path=Path(request['generated']['sources'][0])/'New.java'
    path.write_text(path.read_text().replace('return v','return v.trim()'))
    second=run(settings(),request,tmp_path/'reports',ask=model)
    assert first['input_hash']!=second['input_hash']
    assert model.calls.count('inventory')==1,model.calls


def test_output_inside_inputs_is_rejected(tmp_path):
    request=sources(tmp_path)
    with pytest.raises(ValueError,match='outside input'):
        catalog(request,Path(request['original']['sources'][0])/'work',settings())



def test_related_behaviors_receive_a_separate_interaction_review(tmp_path):
    request=sources(tmp_path)
    seen=[]
    def ask(config,stage,prompt,payload,timeout):
        seen.append(stage);value=answer(stage,payload)
        if stage=='inventory':
            second=dict(value['behaviors'][0],description='Handle null input',conditions='Input is null')
            value['behaviors'].append(second)
        return json.dumps(value)
    report=run(settings(),request,tmp_path/'reports',ask=ask)
    assert report['decision']=='consistent_in_review',report
    assert seen.count('interaction')==1


def test_source_changes_during_review_invalidate_the_result(tmp_path):
    request=sources(tmp_path)
    target=Path(request['original']['sources'][0])/'Old.java'
    changed=False
    def ask(config,stage,prompt,payload,timeout):
        nonlocal changed
        if not changed:
            changed=True;target.write_text(target.read_text()+' // external edit')
        return json.dumps(answer(stage,payload))
    with pytest.raises(ValueError,match='changed during comparison'):
        run(settings(),request,tmp_path/'reports',ask=ask)


def test_evidence_requests_are_fulfilled_without_silent_context_truncation(tmp_path):
    configured=settings();configured['implementation_hash']='test';seen=[]
    def ask(config,stage,prompt,payload,timeout):
        seen.append(payload)
        return json.dumps(dict(need_evidence=['source'])) if not payload['extra_evidence'] else json.dumps(dict(original_evidence=['source']))
    tasks=Tasks(configured,tmp_path/'tasks',{'source':dict(source='return value;')},ask=ask)
    value=tasks.call('test','prompt',{},lambda value:None,{'source'})
    assert value['original_evidence']==['source']
    assert seen[1]['extra_evidence']['source']['source']=='return value;'



def test_helper_field_context_is_available_for_verified_citations(tmp_path):
    request=sources(tmp_path,original='package old; public class Old { public String format(String v){return Util.read(v);} }')
    old=Path(request['original']['sources'][0])
    (old/'Util.java').write_text('package old; public class Util {private static String prefix=""; public static String read(String v){return prefix+v;} }')
    def ask(config,stage,prompt,payload,timeout):
        value=answer(stage,payload)
        if stage in {'compare','interaction'}:
            fields=[identity for identity,chunk in payload['original_evidence'].items() if chunk['kind']=='field']
            if fields: value['original_evidence']=[fields[0]]
        return json.dumps(value)
    report=run(settings(),request,tmp_path/'reports',ask=ask)
    assert report['decision']=='consistent_in_review',report
