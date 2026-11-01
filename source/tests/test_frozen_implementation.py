"""Frozen continuation revalidates code, generates no implementation and refuses Java corrections."""
import json
import pytest
from models.native_implementation import NativeImplementation
from models.native_unit_bundle import NativeUnitBundle
from models.native_test_bundle import NativeTestBundle
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.frozen_implementation import revalidate_frozen
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tools.component_inventory_tools.identity import stable_id
from tests.runtime.test_behavior_conversion import state
from test_staged_pipeline import request,Validator,PKG,CODE,PATH,TEST_PATH,TEST


def test_mutated_frozen_code_is_rejected_before_or_after_validation():
    value=NativeImplementation(files=[{'path':PATH,'content':CODE}]);expected=stable_id(value.model_dump(mode='json'))
    with pytest.raises(VerificationIncomplete,match='hash changed'):revalidate_frozen(value,'wrong',lambda value:None)
    def mutate(copy):copy.files[0].content+='changed'
    with pytest.raises(VerificationIncomplete,match='changed during revalidation'):revalidate_frozen(value,expected,mutate)
    assert value.files[0].content==CODE


@pytest.mark.parametrize('difference',[False,True])
def test_frozen_stage_flow_never_calls_implementation(difference):
    conn,config=state();calls=[];payload=request('response_format')
    payload['sources'][0]['content']='package original; public class Formatter { public String format(String value){return value;} }'
    validator=Validator(differences=int(difference));validator.frozen_implementation=NativeImplementation(files=[{'path':PATH,'content':CODE}])
    validator.frozen_implementation_hash=stable_id(validator.frozen_implementation.model_dump(mode='json'))
    def model(prompt,encoded):
        title=json.loads(encoded)['schema']['title'];calls.append(title)
        assert title!='NativeImplementation'
        if title=='NativeUnitDetails':return json.dumps({'verification_binding':dict(owner_type=PKG+'.Formatter',method_name='format',
            arguments=[dict(type_name='java.lang.String',source='context',key='Value')])})
        assert title=='NativeTestBundle'
        return NativeTestBundle(files=[{'path':TEST_PATH,'content':TEST}],coverage={'r':[TEST_PATH]}).model_dump_json()
    profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
    try:
        with java_scope(profile):
            if difference:
                with pytest.raises(VerificationIncomplete,match='frozen_implementation_requires_change'):
                    generate(conn,config,profile,'unit','unit','Unused combined prompt',payload,NativeUnitBundle,validator,model)
            else:
                result,_=generate(conn,config,profile,'unit','unit','Unused combined prompt',payload,NativeUnitBundle,validator,model)
                assert result.files[0].content==CODE
        assert calls==['NativeUnitDetails','NativeTestBundle']
        assert not conn.execute("SELECT 1 FROM staged_conversion_tasks WHERE stage='implementation' AND attempts>0").fetchone()
        assert validator.frozen_implementation.files[0].content==CODE
        assert conn.execute("SELECT artifact_json FROM staged_conversion_tasks WHERE stage='passing_tests'").fetchone()[0]
    finally:conn.close()


def test_resume_without_model_output_does_not_request_fake_code_correction():
    from runtime.behavior_conversion.stage_tasks import StageTasks
    conn,config=state();requests=[]
    profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
    def model(prompt,encoded):
        value=json.loads(encoded);requests.append(value)
        if len(requests)==1:raise RuntimeError('Prior replay did not allow this provider call')
        return NativeTestBundle(files=[{'path':TEST_PATH,'content':TEST}]).model_dump_json()
    try:
        task=StageTasks(conn,config,profile,'unit','revision',model,None)
        with pytest.raises(RuntimeError):task.ask('tests',{},'Tests only',NativeTestBundle,lambda value:None)
        task=StageTasks(conn,config,profile,'unit','revision',model,None)
        task.ask('tests',{},'Tests only',NativeTestBundle,lambda value:None)
        assert len(requests)==2 and 'previous_model_response' not in requests[1] and 'correction_feedback' not in requests[1]
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='tests'").fetchone()[0]==2
    finally:conn.close()


@pytest.mark.parametrize('invalid',[False,True])
def test_supplied_saved_tests_are_checked_without_model_calls_or_budget_reset(invalid):
    conn,config=state();payload=request('response_format');calls=[]
    payload['sources'][0]['content']='package original; public class Formatter { public String format(String value){return value;} }'
    validator=Validator();validator.frozen_implementation=NativeImplementation(files=[{'path':PATH,'content':CODE}])
    validator.frozen_implementation_hash=stable_id(validator.frozen_implementation.model_dump(mode='json'))
    validator.frozen_tests=NativeTestBundle(files=[{'path':PATH if invalid else TEST_PATH,'content':TEST}],coverage={'r':[TEST_PATH]})
    def model(prompt,encoded):
        title=json.loads(encoded)['schema']['title'];calls.append(title)
        assert title=='NativeUnitDetails'
        return json.dumps({'verification_binding':dict(owner_type=PKG+'.Formatter',method_name='format',
            arguments=[dict(type_name='java.lang.String',source='context',key='Value')])})
    profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
    try:
        with java_scope(profile):
            if invalid:
                with pytest.raises(ValueError,match='Tests-only stage'):
                    generate(conn,config,profile,'unit','unit','Unused',payload,NativeUnitBundle,validator,model)
            else:generate(conn,config,profile,'unit','unit','Unused',payload,NativeUnitBundle,validator,model)
        assert calls==['NativeUnitDetails']
        assert not conn.execute("SELECT 1 FROM staged_conversion_tasks WHERE stage='tests' AND attempts>0").fetchone()
        assert validator.checks==int(not invalid)
    finally:conn.close()
