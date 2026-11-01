"""Failure injection proves bounded role repair without production edits or hidden differences."""
from types import SimpleNamespace
import pytest
from runtime.behavior_conversion.failure_routing import record_correction,adapter_failure,AdapterRepairRequired
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete,comparison_feedback
from tools.state_store_tools import staged_conversion_state as staged
from tests.runtime.test_behavior_conversion import state


def tasks():
    conn,config=state()
    return SimpleNamespace(conn=conn,config=config,identity='unit',revision='revision',profile=SimpleNamespace(max_agent_task_retries=2))


def test_cached_failure_cycle_stops_across_resume_and_feedback_changes():
    task=tasks()
    try:
        staged.reserve(task.conn,task.config.run_id,task.identity,task.revision,'implementation',2,{})
        record_correction(task,'implementation',{'difference':'first'})
        resumed=SimpleNamespace(**vars(task))
        with pytest.raises(VerificationIncomplete,match='no model-attempt progress'):
            record_correction(resumed,'implementation',{'difference':'changed feedback cannot reset progress'})
        staged.reserve(task.conn,task.config.run_id,task.identity,task.revision,'implementation',2,{})
        record_correction(resumed,'implementation',{'difference':'second'})
        with pytest.raises(ValueError,match='budget exhausted'):
            staged.reserve(task.conn,task.config.run_id,task.identity,task.revision,'implementation',2,{})
    finally:task.conn.close()


def test_only_explicit_adapter_provenance_requests_adapter_repair():
    native={'failure_origin':'adapter_binding','issues':['missing method']}
    case={'case':{'case_id':'a'},'native':native,'legacy':{'status':'completed'}}
    report=SimpleNamespace(issues=[],cases=[case])
    assert adapter_failure(report)['stage']=='adapter_invocation'
    native['failure_origin']=None
    assert adapter_failure(report) is None
    native['failure_origin']='adapter_binding';report.issues=['tool changed']
    assert adapter_failure(report) is None


def test_all_proven_differences_are_collected_without_checklist_or_tooling_feedback():
    report=SimpleNamespace(execution_environment={'comparison_policy':'independent-observations-v1'},status='differences_found',issues=[],
        unexecuted_case_ids=[],cases=[{'case':{'case_id':str(n)},'differences':[{'path':'output','legacy':0,'native':1,'related_checklist_ids':['omit']}],
        'limitations':[{'kind':'presence_not_observable'}]} for n in range(12)])
    feedback=comparison_feedback(report)
    assert len(feedback['failing_cases'])==12 and feedback['omitted_failing_case_count']==0
    assert 'incomplete_cases' not in feedback and all('related_checklist_ids' not in case['differences'][0] for case in feedback['failing_cases'])


def test_repeated_cached_adapter_failure_terminates_without_editing_production(monkeypatch):
    from runtime.behavior_conversion.adapter_repair import validate_with_adapter_repair
    task=tasks();production=SimpleNamespace(files=['frozen']);bundle=SimpleNamespace(verification_binding=None);calls=[]
    def adapter(*args,**kwargs):calls.append('adapter');return 'same-invalid-plan'
    monkeypatch.setattr('runtime.behavior_conversion.adapter_repair.resolve_adapter',adapter)
    def validator(*args,**kwargs):raise AdapterRepairRequired({'stage':'adapter_invocation'})
    try:
        with pytest.raises(VerificationIncomplete,match='no model-attempt progress'):
            validate_with_adapter_repair(task,{},production,{},bundle,validator,lambda binding:None)
        assert calls==['adapter','adapter'] and production.files==['frozen']
        assert staged.read(task.conn,task.config.run_id,task.identity,task.revision,'implementation')['attempts']==0
    finally:task.conn.close()


def test_cached_valid_adapter_can_be_revalidated_without_a_new_attempt(monkeypatch):
    from runtime.behavior_conversion.adapter_repair import validate_with_adapter_repair
    task=tasks();bundle=SimpleNamespace(verification_binding='bad');checks=[]
    monkeypatch.setattr('runtime.behavior_conversion.adapter_repair.resolve_adapter',lambda *args,**kwargs:'good')
    def validator(bundle,**kwargs):
        checks.append(bundle.verification_binding)
        if bundle.verification_binding=='bad':raise AdapterRepairRequired({'stage':'adapter_invocation'})
        return {'passed':True}
    try:
        for _ in range(2):
            bundle.verification_binding='bad'
            assert validate_with_adapter_repair(task,{},SimpleNamespace(),{},bundle,validator,lambda binding:None)=={'passed':True}
        assert checks==['bad','good','bad','good']
    finally:task.conn.close()


@pytest.mark.parametrize('message',[
    'Native JavaParser inspection failed: tool class not found',
    'Candidate validation failed: Maven unavailable'])
def test_tool_failures_stop_the_stage_without_a_production_retry(message):
    import json
    from models.pipeline_configuration import PipelineConfiguration
    from models.native_test_bundle import NativeTestBundle
    from runtime.behavior_conversion.stage_tasks import StageTasks
    conn,config=state();calls=[]
    profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
    def model(*args):
        calls.append('tests')
        return json.dumps({'files':[{'path':'src/test/java/T.java','content':'class T {}'}]})
    def check(value):raise ValueError(message)
    task=StageTasks(conn,config,profile,'unit','revision',model,None)
    try:
        with pytest.raises(VerificationIncomplete) as error:
            task.ask('tests',{},'Tests only',NativeTestBundle,check)
        assert error.value.verification_feedback['stage']=='stage_tooling' and calls==['tests']
        assert staged.read(conn,config.run_id,'unit','revision','implementation')['attempts']==0
    finally:conn.close()


def test_production_compiler_errors_escape_tests_role():
    from runtime.behavior_conversion.failure_routing import stage_error
    from runtime.behavior_conversion.compiler_feedback import CompilerCorrectionError
    error=CompilerCorrectionError('invalid code',{'diagnostics':[{'file':'src/main/java/Work.java'}]})
    assert stage_error(error,'tests') is error and error.staged_retry_owner=='implementation'
    same_role=CompilerCorrectionError('invalid code',{'diagnostics':[{'file':'src/main/java/Work.java'}]})
    assert stage_error(same_role,'implementation') is same_role and not getattr(same_role,'staged_retry_owner',None)


def test_provider_failure_resume_keeps_its_role_budget():
    from models.pipeline_configuration import PipelineConfiguration
    from models.native_test_bundle import NativeTestBundle
    from runtime.behavior_conversion.stage_tasks import StageTasks
    conn,config=state();calls=[]
    profile=PipelineConfiguration(model_provider='mock',max_agent_task_retries=2,executable_verification={'mode':'executable_boundary_v1'})
    def provider(*args):calls.append('tests');raise TimeoutError('provider timeout')
    try:
        for _ in range(3):
            task=StageTasks(conn,config,profile,'unit','revision',provider,None)
            with pytest.raises((TimeoutError,ValueError)):
                task.ask('tests',{},'Tests only',NativeTestBundle,lambda value:None)
        assert len(calls)==2 and staged.read(conn,config.run_id,'unit','revision','tests')['attempts']==2
        assert staged.read(conn,config.run_id,'unit','revision','implementation')['attempts']==0
    finally:conn.close()


def test_total_cached_transition_limit_cannot_be_extended_with_new_role_names():
    task=tasks();task.profile.max_agent_task_retries=1
    try:
        for n in range(8):
            staged.reserve(task.conn,task.config.run_id,task.identity,task.revision,'nested'+str(n),1,{})
            record_correction(task,'implementation',{'attempt':n})
        staged.reserve(task.conn,task.config.run_id,task.identity,task.revision,'another',1,{})
        with pytest.raises(VerificationIncomplete,match='transition budget'):
            record_correction(task,'implementation',{'attempt':'cannot reset'})
    finally:task.conn.close()
