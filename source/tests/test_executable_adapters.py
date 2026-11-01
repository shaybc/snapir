"""Restricted adapter plans execute production APIs and cannot fabricate observations."""
import json
from copy import deepcopy
from types import SimpleNamespace
import pytest
from models.native_implementation import NativeImplementation
from models.native_executable_adapter import NativeExecutableAdapter
from models.boundary_case import BoundaryCase
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.unit_verification_boundary import UnitVerificationBoundary
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.native_metadata import inspect_native
from runtime.behavior_conversion.executable_adapters import resolve_adapter
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from runtime.behavior_conversion.stage_tasks import StageTasks
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_verification import verify_boundary
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first
from test_typed_boundary_adapter import ROOT
from tests.runtime.test_behavior_conversion import state

PACKAGE='com.company.generated.adapter'


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


def native():
    bodies={
        'Work':'public class Work { public Result execute(Input input){return new Result(input.getValue());} public int helper(){return 0;} }',
        'Input':'public class Input { private final String value; private Input(String value){this.value=value;} public static Input fromValue(String value){return new Input(value);} public String getValue(){return value;} }',
        'Result':'public class Result { private final String value; public Result(String value){this.value=value;} public String getValue(){return value;} public int getCode(){return 0;} }'}
    return NativeImplementation(files=[dict(path='src/main/java/'+PACKAGE.replace('.','/')+'/'+name+'.java',
        content='package '+PACKAGE+'; '+body) for name,body in bodies.items()])


def recipe():
    return dict(owner_type=PACKAGE+'.Work',method_name='execute',arguments=[dict(type_name=PACKAGE+'.Input',source='object',
        factory_method='fromValue',arguments=[dict(type_name='java.lang.String',source='context',key='value')])],
        context_writes=[dict(context_key='result',getters=['getValue'])],output_getters=['getCode'])


def original():
    return unit(sources=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),
        source('work','''package example; public class Work {
        private com.ibm.dse.base.Context context; public void setContext(com.ibm.dse.base.Context value){context=value;}
        public int execute(){context.setValueAt("result",context.getValueAt("value"));return 0;}
        }''')])


def test_factory_adapter_executes_actual_code_in_separate_jvms(boundary_tool,tmp_path):
    old=original();production=native();metadata=inspect_native(production.files,boundary_tool,old['sources']);calls=[]
    def ask(stage,request,instruction,schema,check):
        calls.append(stage);assert request['production_files'] and 'expected_outputs' not in request
        value=schema(binding=recipe());check(value);return value
    payload=dict(old,requirements={'business':'Preserve original writes and result'})
    binding=resolve_adapter(SimpleNamespace(ask=ask),payload,production,metadata)
    assert calls==['adapter'] and binding.arguments[0].factory_method=='fromValue'
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(old),tool_jar=boundary_tool)))
    left=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
    right=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',sources=production.files,native_entry=binding)
    cases=[BoundaryCase(case_id='null',initial_context={'value':None}),BoundaryCase(case_id='text',initial_context={'value':'hello'})]
    report=verify_boundary(old,boundary,left,right,cases,tmp_path/'factory',tool=boundary_tool,candidate_label='factory_adapter_fixture')
    assert report.status=='matched_observed_cases',report.model_dump_json(indent=2)
    assert all(any('Work.execute' in probe['id'] for probe in case['native']['probes']) for case in report.cases)
    assert report.cases[1]['native']['context']['result']=='hello'
    before=production.model_dump_json()
    right=right.model_copy(deep=True)
    right.sources[0].content=right.sources[0].content.replace('input.getValue()','"invented"')
    changed=verify_boundary(old,boundary,left,right,cases,tmp_path/'defect',tool=boundary_tool,candidate_label='deliberate_production_defect')
    assert changed.status=='differences_found'
    assert production.model_dump_json()==before


def test_adapter_cannot_return_constants_or_skip_the_entry(boundary_tool):
    production=native();old=original();metadata=inspect_native(production.files,boundary_tool,old['sources'])
    for forbidden in ({'source':'return 0;'}, {'expected':0}, {'files':[]}):
        with pytest.raises(ValueError):NativeExecutableAdapter.model_validate(dict(binding=recipe(),**forbidden))
    bad=recipe();bad['method_name']='helper'
    def ask(stage,request,instruction,schema,check):
        value=schema(binding=bad);check(value);return value
    with pytest.raises(VerificationIncomplete,match='configured boundary entry'):
        resolve_adapter(SimpleNamespace(ask=ask),dict(old,requirements={'r':'Preserve'}),production,metadata)


def test_alternative_constant_entry_cannot_be_selected_as_the_target(boundary_tool):
    from models.native_unit_bundle import NativeSourceFile
    production=native();old=original()
    production.files.append(NativeSourceFile(path='src/main/java/'+PACKAGE.replace('.','/')+'/FakeEntry.java',
        content='package '+PACKAGE+'; public class FakeEntry { public int execute(){return 0;} }'))
    metadata=inspect_native(production.files,boundary_tool,old['sources'])
    def forbidden(*args):raise AssertionError('Ambiguous entry must not be chosen by the model')
    with pytest.raises(VerificationIncomplete,match='entry owner is missing or ambiguous'):
        resolve_adapter(SimpleNamespace(ask=forbidden),dict(old,requirements={'r':'Preserve'}),production,metadata)


def test_adapter_budget_is_separate_and_cannot_reset_on_resume(boundary_tool):
    production=native();old=original();metadata=inspect_native(production.files,boundary_tool,old['sources'])
    conn,config=state();calls=[];before=production.model_dump_json()
    def model(prompt,text):
        request=json.loads(text);calls.append(request)
        assert request['schema']['title']=='NativeExecutableAdapter'
        bad=recipe();bad['arguments'][0]['factory_method']='missingFactory'
        return NativeExecutableAdapter(binding=bad).model_dump_json()
    profile=PipelineConfiguration(model_provider='mock',max_agent_task_retries=2)
    tasks=StageTasks(conn,config,profile,'fixture','frozen-production',model,SimpleNamespace())
    try:
        for _ in range(2):
            with pytest.raises(VerificationIncomplete,match='adapter'):
                resolve_adapter(tasks,dict(old,requirements={'r':'Preserve'}),production,metadata)
        assert len(calls)==2 and production.model_dump_json()==before
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='adapter'").fetchone()[0]==2
        assert not conn.execute("SELECT 1 FROM staged_conversion_tasks WHERE stage='implementation'").fetchone()
    finally:conn.close()


def test_declared_limitation_does_not_trigger_code_repairs(boundary_tool):
    production=native();old=original();metadata=inspect_native(production.files,boundary_tool,old['sources']);calls=[]
    def ask(stage,request,instruction,schema,check):
        calls.append(stage);value=schema(limitation='Repeated dynamic writes require an unsupported observer');check(value)
    with pytest.raises(VerificationIncomplete,match='unsupported observer'):
        resolve_adapter(SimpleNamespace(ask=ask),dict(old,requirements={'r':'Preserve'}),production,metadata)
    assert calls==['adapter']


def test_xml_configured_context_keys_are_known_without_literal_reads(boundary_tool):
    production=native();old=original();old['kind']='response_format'
    old['effective_configuration']={'attributes':{},'children':[{'attributes':{'dataName':'value'},'children':[]}]}
    production.files[0].content='package '+PACKAGE+'; public class Work { public String format(Input input){return input.getValue();} }'
    metadata=inspect_native(production.files,boundary_tool)
    assert not metadata['context_keys']
    binding=recipe();binding.update(method_name='format',context_writes=[],output_getters=[])
    def ask(stage,request,instruction,schema,check):
        value=schema(binding=binding);check(value);return value
    result=resolve_adapter(SimpleNamespace(ask=ask),dict(old,requirements={'r':'Preserve'}),production,metadata)
    assert result.arguments[0].arguments[0].key=='value'


def test_staged_format_uses_separate_adapter_and_retains_frozen_code(monkeypatch):
    from models.native_format_component_bundle import NativeFormatComponentBundle
    from models.native_test_bundle import NativeTestBundle
    from runtime.behavior_conversion.generation import generate
    from test_staged_pipeline import request,Validator,TEST_PATH,TEST
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    production=native()
    production.files[0].content='package '+PACKAGE+'; public class Work { public String format(Input input){return input.getValue();} }'
    payload=request('format_composition');payload['configured_format']=dict(original(),kind='response_format')
    payload['sources']=[source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),source('source',
        'package original; public class Formatter { public String format(com.ibm.dse.base.Context context){return (String)context.getValueAt("value");} }')]
    before=production.model_dump_json();calls=[]
    binding=recipe();binding['method_name']='format';binding['context_writes']=[];binding['output_getters']=[]
    def model(prompt,text):
        req=json.loads(text);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return production.model_dump_json()
        if title=='NativeFormatComponentDetails':return json.dumps({'component_details':{},'verification_binding':None})
        if title=='NativeExecutableAdapter':return NativeExecutableAdapter(binding=binding).model_dump_json()
        assert title=='NativeTestBundle'
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)],coverage={'r':[TEST_PATH]}).model_dump_json()
    conn,config=state()
    try:
        profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
        result,_=generate(conn,config,profile,'component_generation','unit','Unused combined instructions',payload,
            NativeFormatComponentBundle,validator=Validator(),model_call=model)
        assert calls==['NativeImplementation','NativeFormatComponentDetails','NativeExecutableAdapter','NativeTestBundle']
        assert result.verification_binding.arguments[0].factory_method=='fromValue'
        assert production.model_dump_json()==before
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='adapter'").fetchone()[0]==1
    finally:conn.close()


def test_component_step_promotion_uses_the_adapter_role(boundary_tool):
    from models.native_unit_bundle import NativeUnitBundle
    from runtime.component_conversion.unit_binding import native_unit_binding
    production=native();old=original();calls=[];validated=[]
    parsed=inspect_native(production.files,boundary_tool,old['sources'])
    artifacts=dict(root_report={'owned_sources':[f.path for f in production.files]},
        files={f.path:f.content for f in production.files},proof={'unit_id':old['unit_id']},contract={'apis':parsed['apis']})
    configured=SimpleNamespace(**old,logical_id='fixture-step',model_dump=lambda **kwargs:deepcopy(old))
    def build(value):
        return NativeUnitBundle(files=production.files,unit_contract=dict(unit_id=old['unit_id'],apis=parsed['apis'],
            requirements={'r':'Preserve'},evidence_ids=['work']),verification_binding=value.verification_binding)
    def model(prompt,text):
        req=json.loads(text);calls.append(req['schema']['title'])
        assert req['component_proof']==artifacts['proof']
        return NativeExecutableAdapter(binding=recipe()).model_dump_json()
    conn,config=state()
    try:
        profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
        bundle=native_unit_binding(conn,config,profile,configured,artifacts,build,
            lambda value,cached=False:validated.append(value),model)
        assert calls==['NativeExecutableAdapter'] and validated==[bundle]
        assert bundle.verification_binding.arguments[0].factory_method=='fromValue'
    finally:conn.close()
