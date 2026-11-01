"""Precise, aggregate citation checks and bounded exact evidence selection."""
import hashlib
import json
import pytest
from models.pipeline_configuration import PipelineConfiguration
from runtime.behavior_conversion.metadata_checklist_validation import validate_batch,validate_component_mappings
from runtime.behavior_conversion.metadata_checklist_batches import plan_batches,build_request,EvidenceTooLarge
from runtime.behavior_conversion.metadata_checklist_evidence import source_catalog

PATH='src/main/java/com/company/generated/Work.java'
CODE='package com.company.generated; public class Work { public int execute(){return 0;} }'
ORIGINAL='package original; public class Work { public int execute(){return 0;} }'


def items(n=6):
    return [dict(id='item-'+str(i),code_node_id='method',source_identity='original',source_hash=hashlib.sha256(ORIGINAL.encode()).hexdigest(),
        start_line=1,end_line=1,detail='return',excerpt='return 0;') for i in range(n)]


def answer(key,excerpt='return 0;',path=PATH):
    return dict(checklist_id=key,status='implemented',locations=[dict(path=path,excerpt=excerpt)])


def envelope(entries):return dict(task_revision='r',production_revision='p',batch_id='b',entries=entries)


def test_all_detectable_errors_and_independent_successes_are_returned():
    result=validate_batch(envelope([answer('a'),answer('b','absent'),answer('c'),answer('c'),answer('unknown'),answer('e',path='../bad'),7]),
        ['a','b','c','d','e'],{PATH:CODE},revision='r',production='p',batch_id='b')
    assert set(result['accepted'])=={'a'}
    assert {'excerpt_not_found','duplicate_item','unknown_item','missing_item','unsafe_path','malformed_entry'}<=set(e['code'] for e in result['errors'])


def test_stale_or_malformed_envelopes_cannot_retain_anything():
    for raw in (None,dict(envelope([answer('a')]),production_revision='old')):
        result=validate_batch(raw,['a'],{PATH:CODE},revision='r',production='p',batch_id='b')
        assert not result['accepted'] and result['errors']


def test_unshown_code_and_unapproved_component_exclusions_are_not_accepted():
    result=validate_batch(envelope([answer('a'),dict(checklist_id='b',status='not_applicable',reason='framework_plumbing',rule_id='invented')]),
        ['a','b'],{PATH:CODE},revision='r',production='p',batch_id='b',visible={PATH:['public class Work']})
    assert {e['code'] for e in result['errors']}=={'evidence_unavailable','unsupported_exclusion'}


def test_final_owner_collects_missing_and_invalid_locations_together():
    with pytest.raises(ValueError) as error:validate_component_mappings({'a':[dict(path=PATH,excerpt='absent')]},{'a','b'},{PATH:CODE})
    assert 'excerpt_not_found' in str(error.value) and 'missing_item' in str(error.value)


def test_batches_are_stable_method_grouped_and_count_bounded():
    values=items(35)
    assert plan_batches(values,15)==plan_batches(list(reversed(values)),15)
    assert [len(g) for g in plan_batches(values,15)]==[15,15,5]


def test_complete_size_includes_guidance_schema_unicode_and_reserve():
    payload={'sources':[dict(identity='original',content=ORIGINAL,content_hash=hashlib.sha256(ORIGINAL.encode()).hexdigest())]}
    catalog=source_catalog(payload,{PATH:CODE+' // שלום 😀'},{});values={i['id']:i for i in items(2)}
    profile=PipelineConfiguration(metadata_checklist_request_chars=40000,metadata_checklist_response_chars=4000)
    req,encoded=build_request(list(values),values,catalog,profile,'r','p')
    assert req['entry_schema'] and req['composer_behavior_evidence'] and req['evidence_catalog']
    assert len(encoded)+len(__import__('agents.behavior_conversion.metadata_checklist',fromlist=['MAPPING']).MAPPING)<=36000
    assert len(encoded.encode())>len(encoded)


def test_oversized_single_item_never_truncates_source():
    original=ORIGINAL+' '*90000
    payload={'sources':[dict(identity='original',content=original)]}
    catalog=source_catalog(payload,{PATH:CODE},{})
    value=items(1)[0];value['source_hash']=hashlib.sha256(original.encode()).hexdigest()
    with pytest.raises(EvidenceTooLarge):build_request([value['id']],{value['id']:value},catalog,
        PipelineConfiguration(metadata_checklist_request_chars=20000,metadata_checklist_response_chars=2000),'r','p')
