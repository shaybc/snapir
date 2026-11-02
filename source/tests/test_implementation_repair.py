"""Implementation corrections keep explicit rules, precise defects and honest baseline evidence."""
from copy import deepcopy
from contextlib import nullcontext
import json
import pytest
from agents.behavior_conversion.staged_pipeline import code_instruction
from models.native_implementation import NativeImplementation
from models.pipeline_configuration import PipelineConfiguration
from runtime.behavior_conversion.implementation_repair import repair_baseline,focused_repair
from runtime.behavior_conversion.stage_tasks import StageTasks
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools import staged_conversion_state as staged
from tests.runtime.test_behavior_conversion import state


def candidate():
    return NativeImplementation(files=[dict(path='src/main/java/example/Step.java',
        content='package example; public class Step { public void setService(String name, Object service) {} public int execute() { return 0; } }')]).model_dump(mode='json')


def records():
    value=candidate()
    proof=dict(production_hash=stable_id(value),validation=dict(build_passed=True))
    return (dict(artifact_json=json.dumps(value),artifact_hash=stable_id(value)),
        dict(artifact_json=json.dumps(proof),artifact_hash=stable_id(proof)))


def test_mandatory_rules_lead_initial_and_correction_prompt():
    prompt=code_instruction({'kind':'configured_step'})
    assert prompt.startswith('MANDATORY IMPLEMENTATION CONTRACT')
    for text in ['No IBM','Object/Object[]','accepted native APIs unchanged','valid JSON','preserve','complete corrected files']:
        assert text in prompt


def test_typed_defect_identifies_file_method_and_last_compiled_baseline():
    baseline=repair_baseline(*records())
    feedback=dict(error='Typed boundary requires scalar or native DTO inputs/results, not generic state: public void setService(java.lang.String, java.lang.Object). Derive fields from supplied XML/source evidence;',
        previous_implementation=candidate())
    request=dict(implementation_feedback=feedback,sources=[{'content':'complete original evidence'}])
    before=deepcopy(request)
    result=focused_repair(request,baseline)['implementation_repair']
    assert result['locations']==[dict(file='src/main/java/example/Step.java',method='public void setService(java.lang.String, java.lang.Object)')]
    assert result['baseline']['candidate']==candidate()
    assert result['baseline']['passed_checks']==['production_compilation']
    assert result['baseline']['acceptance'] is False
    assert request==before


def test_mismatched_or_tampered_proof_never_claims_validation():
    implementation,compiled=records()
    compiled['artifact_hash']='tampered'
    assert repair_baseline(implementation,compiled) is None
    implementation,compiled=records();value=json.loads(implementation['artifact_json'])
    value['files'][0]['content']+=' changed'
    implementation.update(artifact_json=json.dumps(value),artifact_hash=stable_id(value))
    assert repair_baseline(implementation,compiled) is None
    result=focused_repair({'correction_feedback':'Invalid JSON','previous_model_response':'broken'},None)
    assert result['implementation_repair']['locations']==[]
    assert 'No hash-matched compiled candidate' in result['implementation_repair']['baseline_status']


def test_compile_diagnostics_and_original_feedback_are_preserved():
    request=dict(correction_feedback='Cannot resolve method',compiler_correction=dict(diagnostics=[
        dict(file='src/main/java/example/Step.java',line=8,column=4,message='missing method')]))
    result=focused_repair(request,None)
    assert result['compiler_correction']==request['compiler_correction']
    assert result['implementation_repair']['locations'][0]['line']==8
    assert focused_repair({'sources':['unchanged']},None)=={'sources':['unchanged']}


def test_stage_calls_include_baseline_on_retries_without_resetting_budget(monkeypatch):
    from runtime.behavior_conversion import generation,stage_scope
    conn,config=state();seen=[]
    try:
        implementation,compiled=records()
        staged.retain(conn,config.run_id,'unit','revision','implementation',candidate(),implementation['artifact_hash'])
        staged.retain(conn,config.run_id,'unit','revision','compile',json.loads(compiled['artifact_json']),compiled['artifact_hash'])
        def generate(*args,model_call,validator,**kwargs):
            instruction=args[5];request=args[6]
            first=dict(request,correction_feedback='Prohibited framework dependency in src/main/java/example/Step.java: com.ibm')
            model_call(instruction,json.dumps(first))
            second=dict(request,correction_feedback='Invalid JSON',previous_model_response='broken')
            raw=model_call(instruction,json.dumps(second))
            value=NativeImplementation.model_validate_json(raw);validator(value)
            return value,'fingerprint'
        monkeypatch.setattr(generation,'_generate',generate)
        monkeypatch.setattr(stage_scope,'authorized_stage',lambda *args:nullcontext())
        def model(instruction,encoded):
            seen.append(json.loads(encoded));assert instruction.startswith('MANDATORY IMPLEMENTATION CONTRACT')
            return json.dumps(candidate())
        profile=PipelineConfiguration(model_provider='mock',max_agent_task_retries=2)
        tasks=StageTasks(conn,config,profile,'unit','revision',model,lambda value:None)
        tasks.ask('implementation',{},code_instruction({}),NativeImplementation,lambda value:None)
        assert len(seen)==2
        assert seen[0]['implementation_repair']['locations']==[dict(file='src/main/java/example/Step.java')]
        assert all(request['implementation_repair']['baseline']['candidate']==candidate() for request in seen)
        row=staged.read(conn,config.run_id,'unit','revision','implementation')
        assert row['attempts']==2
        with pytest.raises(ValueError,match='budget exhausted'):
            tasks.ask('implementation',{},code_instruction({}),NativeImplementation,lambda value:None)
        assert len(seen)==2
        requests=[json.loads(row[0]) for row in conn.execute('select request_json from staged_conversion_attempts order by attempt')]
        assert requests==seen
    finally:conn.close()


def test_oversized_repair_stops_before_reserving_or_calling_model(monkeypatch):
    from runtime.behavior_conversion import generation,stage_scope
    conn,config=state();calls=[]
    try:
        value=candidate();value['files'][0]['content']+=' ' * 65000
        proof=dict(production_hash=stable_id(value),validation=dict(build_passed=True))
        staged.retain(conn,config.run_id,'unit','revision','implementation',value,stable_id(value))
        staged.retain(conn,config.run_id,'unit','revision','compile',proof,stable_id(proof))
        def generate(*args,model_call,**kwargs):
            model_call(args[5],json.dumps({'correction_feedback':'Invalid JSON'}))
        monkeypatch.setattr(generation,'_generate',generate)
        monkeypatch.setattr(stage_scope,'authorized_stage',lambda *args:nullcontext())
        tasks=StageTasks(conn,config,PipelineConfiguration(model_provider='mock',behavior_context_chars=60000),
            'unit','revision',lambda *args:calls.append(args),lambda value:None)
        with pytest.raises(ValueError,match='context budget'):
            tasks.ask('implementation',{},code_instruction({}),NativeImplementation,lambda value:None)
        assert calls==[]
        assert staged.read(conn,config.run_id,'unit','revision','implementation')['attempts']==0
    finally:conn.close()
