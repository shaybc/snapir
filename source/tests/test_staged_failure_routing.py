"""The registered pipeline repairs adapter wiring without regenerating code or passing tests."""
import json
from models.pipeline_configuration import PipelineConfiguration
from models.native_unit_bundle import NativeUnitBundle
from models.native_test_bundle import NativeTestBundle
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.failure_routing import AdapterRepairRequired
from runtime.java_toolchain import java_scope
from tests.runtime.test_behavior_conversion import state
from test_staged_pipeline import request,metadata,Validator,PKG,CODE,PATH,TEST_PATH,TEST


def test_full_stage_flow_routes_adapter_failure_to_adapter_only():
    conn,config=state();calls=[];payload=request('response_format')
    payload['sources'][0]['content']='package original; public class Formatter { public String format(String value){return value;} }'
    payload.update(effective_configuration={'attributes':{'dataName':'Value'},'children':[]},referenced_definitions=[],configuration_xml='<format/>')
    binding=dict(owner_type=PKG+'.Formatter',method_name='format',arguments=[dict(type_name='java.lang.String',source='context',key='Value')])
    class FailingAdapter(Validator):
        def __call__(self,bundle,cached=False):
            super().__call__(bundle,cached=cached)
            if self.checks==1:raise AdapterRepairRequired(dict(stage='adapter_invocation',errors=['injected trusted wiring failure']))
    validator=FailingAdapter()
    def model(prompt,encoded):
        value=json.loads(encoded);kind=value['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':return json.dumps({'files':[{'path':PATH,'content':CODE}]})
        if kind=='NativeUnitDetails':return json.dumps({'verification_binding':binding})
        if kind=='NativeExecutableAdapter':
            assert value['adapter_feedback']['stage']=='adapter_invocation'
            return json.dumps({'binding':binding})
        assert kind=='NativeTestBundle'
        return NativeTestBundle(files=[{'path':TEST_PATH,'content':TEST}],coverage={'r':[TEST_PATH]}).model_dump_json()
    profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
    try:
        with java_scope(profile):
            result,_=generate(conn,config,profile,'unit','unit','Unused combined instructions',payload,NativeUnitBundle,validator,model)
        assert calls==['NativeImplementation','NativeUnitDetails','NativeTestBundle','NativeExecutableAdapter']
        assert validator.checks==2 and result.files[0].content==CODE
        counts=dict(conn.execute('SELECT stage,attempts FROM staged_conversion_tasks WHERE attempts>0').fetchall())
        assert counts=={'implementation':1,'semantic_metadata':1,'tests':1,'adapter':1}
        assert conn.execute("SELECT artifact_json FROM staged_conversion_tasks WHERE stage='passing_tests'").fetchone()[0]
    finally:conn.close()
