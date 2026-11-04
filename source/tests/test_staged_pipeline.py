"""Exercise all registered full-converter stage paths without claiming mock receipts prove equivalence."""
import json
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from models.native_unit_bundle import NativeUnitBundle
from models.native_component_bundle import NativeComponentBundle
from models.native_format_component_bundle import NativeFormatComponentBundle
from models.operation_data_contract import OperationDataContract
from models.staged_metadata import metadata_schema
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete
from runtime.behavior_conversion.conversion_tasks import conversion_task
from runtime.java_toolchain import java_scope
from tests.runtime.test_behavior_conversion import state

PKG='com.company.generated.full'
PATH='src/main/java/'+PKG.replace('.','/')+'/Formatter.java'
CODE='package '+PKG+'; public class Formatter { public String format(String value){ return value; } }'
TEST_PATH='src/test/java/'+PKG.replace('.','/')+'/FormatterTest.java'
TEST='package '+PKG+'; public class FormatterTest {}'
API=dict(type_name=PKG+'.Formatter',method_signatures=['public String format(String value)'])
UNIT=dict(unit_id='unit',apis=[API],requirements={'r':'Preserve'},evidence_ids=['source'])


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


def request(kind='response_format'):
    return dict(kind=kind,unit_id='unit',requirements={'r':'Preserve'},sources=[dict(identity='source',content='original')],
        expected_contract_fields={'component':dict(component_id='component',source_entry_points=['original.format'],
            evidence_ids=['source'],dependencies=[],configuration_mode='parameterized')},parser_checklist=[])


def metadata(schema):
    if schema in (NativeComponentBundle,NativeFormatComponentBundle):
        data=dict(contracts={'component':dict(component_id='component',apis=[API],source_entry_points=['original.format'],
            evidence_ids=['source'],dependencies=[],configuration_mode='parameterized')},evidence_ids=['source'])
        if schema is NativeFormatComponentBundle:
            data.update(checklist_answers=dict(unit_id='unit',source_manifest_hash='source',configuration_hash='config'),
                verification_binding=dict(owner_type=PKG+'.Formatter',method_name='format',arguments=[dict(type_name='java.lang.String',source='context',key='Value')]))
        return data
    if schema is OperationDataContract:
        return dict(units=[UNIT],service_api=API,request_type='java.lang.String',success_type='java.lang.String',error_type='java.lang.String')
    return dict(unit_contract=UNIT,evidence_ids=['source'])


class Validator:
    """Flow-only stub; real JVM/Maven coverage is exercised by separate adapter tests."""
    def __init__(self,differences=0):self.compiles=0;self.checks=0;self.differences=differences;self.last=None
    def compile_implementation(self,bundle):
        self.compiles+=1
        assert all(f.path.startswith('src/main/java/') for f in bundle.files)
        return dict(build_passed=True)
    def __call__(self,bundle,cached=False):
        self.checks+=1
        if hasattr(bundle,'files'):validate_bundle(NativeUnitBundle(files=bundle.files),allowed_classes=[])
        self.last=dict(build_validation=dict(build_passed=True,tests_passed=True,test_count=1))
        if self.checks<=self.differences:raise VerificationFailure(dict(stage='boundary',failing_cases=[dict(input='x',expected='a',actual='b')]))


@pytest.mark.parametrize('schema,kind',[(NativeComponentBundle,'basic_component'),
    (NativeFormatComponentBundle,'format_composition'),(NativeUnitBundle,'response_format')])
def test_executable_mode_omits_checklist_mapping(monkeypatch,schema,kind):
    """The opt-in path never sends an exhaustive checklist to the model."""
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    def forbidden(*args,**kwargs):raise AssertionError('Checklist mapping must not run')
    monkeypatch.setattr('runtime.behavior_conversion.metadata_checklist.map_checklist',forbidden)
    conn,config=state();calls=[];payload=request(kind)
    payload['sources'][0]['content']='package original; public class Formatter { public String format(String value){return value;} }'
    payload['parser_checklist']=[dict(id='must-not-map')]
    payload['checklist']={'items':[dict(id='must-not-map')]}
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        assert 'must-not-map' not in encoded
        if title=='NativeImplementation':return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
        if title==schema.__name__.replace('Bundle','Details'):
            assert 'contracts' not in req['schema']['properties'] and 'unit_contract' not in req['schema']['properties']
            data={'component_details':{}} if 'contracts' in schema.model_fields else {}
            if schema is NativeFormatComponentBundle:
                data['verification_binding']=metadata(schema)['verification_binding']
            elif schema is NativeUnitBundle:
                data['verification_binding']=dict(owner_type=PKG+'.Formatter',method_name='format',
                    arguments=[dict(type_name='java.lang.String',source='context',key='Value')])
            return json.dumps(data)
        assert title=='NativeTestBundle'
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)],coverage={'r':[TEST_PATH]}).model_dump_json()
    try:
        profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'})
        result,_=generate(conn,config,profile,'component_generation','unit','Unused combined instructions',payload,
            schema,validator=Validator(),model_call=model)
        assert not getattr(result,'checklist_implementations',{}) and len(result.files)==2
        contract=result.contracts['component'] if hasattr(result,'contracts') else result.unit_contract
        assert contract.apis[0].type_name==PKG+'.Formatter'
        assert calls==['NativeImplementation',schema.__name__.replace('Bundle','Details'),'NativeTestBundle']
    finally:conn.close()


@pytest.mark.parametrize('category,schema,kind',[
    ('component_generation',NativeComponentBundle,'basic_component'),
    ('component_generation',NativeComponentBundle,'configured_step'),
    ('component_generation',NativeComponentBundle,'format_subtree'),
    ('component_generation',NativeFormatComponentBundle,'format_composition'),
    ('unit',NativeUnitBundle,'response_format'),
    ('unit',NativeUnitBundle,'request_unformat'),
    ('unit',NativeUnitBundle,'configured_step'),
    ('service',NativeUnitBundle,'service'),
    ('side_road_baseline',NativeUnitBundle,'response_format'),
    ('side_road_simplify',NativeUnitBundle,'response_format'),
])
def test_registered_code_jobs_split_code_metadata_tests_and_reuse_after_difference(monkeypatch,category,schema,kind):
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    conn,config=state();validator=Validator(differences=1);calls=[];payload=request(kind)
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':
            assert 'parser_checklist' not in req and 'testing_contract' not in req and 'expected_contract_fields' not in req
            assert 'source_entry_points' not in req.get('schema',{}).get('properties',{})
            assert 'original' in json.dumps(req['sources'])
            return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
        if title==metadata_schema(schema).__name__:
            assert req['parsed_apis']['apis'] and req['production_files']
            assert 'files' not in req['schema']['properties'] and 'dependencies' not in req['schema']['properties']
            return json.dumps(metadata(schema))
        assert title=='NativeTestBundle'
        assert 'contracts' not in req['schema']['properties'] and 'production_files' in req
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)],coverage={'r':[TEST_PATH]}).model_dump_json()
    try:
        result,_=generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            category,'unit','Old combined instructions must not be used',payload,schema,validator=validator,model_call=model)
        assert calls.count('NativeImplementation')==2 and calls.count('NativeTestBundle')==1
        assert validator.compiles==2 and validator.checks==2
        assert len(result.files)==2
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='tests'").fetchone()[0]==1
    finally:conn.close()


def test_contract_structure_then_dto_code_then_real_existing_contract_validation():
    conn,config=state();validator=Validator();calls=[];payload=request();payload['units']=[{'unit_id':'unit'}]
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='OperationContractMetadata':
            assert 'sources' not in req['schema']['properties']
            return json.dumps(metadata(OperationDataContract))
        assert title=='NativeImplementation' and req['planned_structure']['units']
        return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
    try:
        result,_=generate(conn,config,PipelineConfiguration(model_provider='mock'),'contract','op','unused',payload,
            OperationDataContract,validator=validator,model_call=model)
        assert calls==['OperationContractMetadata','NativeImplementation']
        assert result.sources[0]['content']==CODE and validator.compiles==validator.checks==1
    finally:conn.close()


@pytest.mark.parametrize('kind',['service_implementation','route_scenario_test'])
def test_assembly_code_and_route_tests_keep_their_separate_responsibilities(kind):
    conn,config=state();validator=Validator();calls=[]
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
        if title=='NativeUnitMetadata':return json.dumps(metadata(NativeUnitBundle))
        assert title=='NativeTestBundle'
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)]).model_dump_json()
    try:
        bundle,_=generate(conn,config,PipelineConfiguration(model_provider='mock'),kind,'op','unused',request(),NativeUnitBundle,
            validator=validator,model_call=model)
        assert calls==(['NativeImplementation','NativeUnitMetadata'] if kind=='service_implementation' else ['NativeTestBundle'])
        assert all(f.path.startswith('src/test/java/') for f in bundle.files) if kind=='route_scenario_test' else len(bundle.files)==1
    finally:conn.close()


def test_provisional_operation_interface_failure_returns_to_the_implementation_budget():
    from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
    conn,config=state();calls=[]
    class OperationValidator(Validator):
        def __call__(self,bundle,cached=False):
            super().__call__(bundle,cached)
            if self.checks==1:raise ImplementationInterfaceError('Operation constructor must store the supplied step')
    validator=OperationValidator()
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':
            if calls.count(title)==2:assert req['implementation_feedback']['stage']=='implementation_interface'
            return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
        assert title=='NativeUnitMetadata'
        return json.dumps(metadata(NativeUnitBundle))
    try:
        result,_=generate(conn,config,PipelineConfiguration(model_provider='mock'),'service_implementation','op','unused',request('service'),
            NativeUnitBundle,validator=validator,model_call=model)
        assert len(result.files)==1 and validator.checks==validator.compiles==2
        assert calls.count('NativeImplementation')==2 and 'NativeTestBundle' not in calls
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='implementation'").fetchone()[0]==2
    finally:conn.close()


def test_operation_metadata_feedback_is_corrected_without_regenerating_java():
    conn,config=state();calls=[]
    class OperationValidator(Validator):
        def validate_metadata(self,bundle):
            if bundle.output_type!='java.lang.String':raise ValueError('Operation contract must describe the compiled String result')
    validator=OperationValidator()
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
        assert title=='NativeUnitMetadata'
        data=metadata(NativeUnitBundle)
        if calls.count(title)>1:data['output_type']='java.lang.String'
        return json.dumps(data)
    try:
        result,_=generate(conn,config,PipelineConfiguration(model_provider='mock'),'service_implementation','op','unused',request('service'),
            NativeUnitBundle,validator=validator,model_call=model)
        assert result.output_type=='java.lang.String'
        assert calls.count('NativeImplementation')==1 and calls.count('NativeUnitMetadata')==2
        assert validator.compiles==1 and validator.checks==1
    finally:conn.close()


def test_unknown_code_task_and_missing_compile_adapter_fail_before_model_call():
    assert PipelineConfiguration().staged_unit_conversion is True
    assert conversion_task('route_test_plan',type('RouteTestPlan',(),{}))=='metadata'
    with pytest.raises(ValueError,match='registered'):conversion_task('invented',NativeUnitBundle)
    conn,config=state()
    try:
        with pytest.raises(VerificationIncomplete,match='compile-only'):
            generate(conn,config,PipelineConfiguration(model_provider='mock'),'unit','unit','unused',request(),NativeUnitBundle,
                validator=lambda *a:None,model_call=lambda *a:pytest.fail('No model before adapter readiness'))
    finally:conn.close()


def test_parent_component_scope_is_checked_before_any_stage_or_model():
    conn,config=state()
    try:
        with pytest.raises(ValueError,match='gated'):
            generate(conn,config,PipelineConfiguration(model_provider='mock'),'component_generation','unit','unused',request(),
                NativeComponentBundle,validator=Validator(),model_call=lambda *a:pytest.fail('No unauthorized call'))
    finally:conn.close()


def test_feedback_and_dependency_advice_cannot_reset_role_identity():
    from runtime.behavior_conversion.staged_adapters import task_revision_payload
    first=request();second=dict(first,whole_unit_feedback={'difference':'new'},final_validation_feedback={'changed':True},
        known_dependencies=[{'group_id':'new-advice'}])
    assert task_revision_payload(first)==task_revision_payload(second)
    changed=dict(first,sources=[dict(identity='source',content='changed original')])
    assert task_revision_payload(first)!=task_revision_payload(changed)


def test_stage_authorization_uses_original_profile_and_rechecks_each_role(monkeypatch):
    from runtime.behavior_conversion.stage_scope import authorized_stage,verify_stage
    calls=[];conn,config=state();profile=PipelineConfiguration(model_provider='mock')
    def verify():calls.append('checked')
    try:
        with authorized_stage(conn,config,profile,'staged_tests','unit:revision',verify):
            assert verify_stage(conn,config,profile,'staged_tests','unit:revision')
            with pytest.raises(ValueError,match='authorized parent'):
                verify_stage(conn,config,profile.model_copy(),'staged_tests','unit:revision')
        assert calls==['checked','checked']
        assert not verify_stage(conn,config,profile,'staged_tests','unit:revision')
    finally:conn.close()


@pytest.mark.parametrize('batched',[False,True])
def test_real_maven_staged_component_compilation_tests_and_unchanged_resume(tmp_path,monkeypatch,batched):
    from tests.runtime.test_scoped_native import actual_build
    from runtime.behavior_conversion.stage_compilation import production_compiler
    from runtime.behavior_conversion.bundle_output import accept_bundle
    from runtime.behavior_conversion.testing_contract import attach_testing_contract
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    conn,config=state();profile=PipelineConfiguration(model_provider='mock',java_version=25)
    payload=request();attach_testing_contract(payload,profile)
    if batched:
        from test_metadata_checklist import items,ORIGINAL
        payload['sources']=[dict(identity='original',content=ORIGINAL)]
        payload['parser_checklist']=items(2)
    class RealValidator:
        compile_implementation=staticmethod(production_compiler(profile,actual_build))
        last=None
        def __call__(self,bundle,cached=False):
            native=NativeUnitBundle(files=bundle.files,dependencies=bundle.dependencies,coverage=bundle.coverage)
            files=validate_bundle(native,requirements=payload['requirements'])
            receipt,_=accept_bundle(tmp_path/'native',files,actual_build,profile,bundle.dependencies,require_tests=True,
                required_tests=[TEST_PATH],testing_contract=payload['testing_contract'],
                owned_files=files.keys() if (tmp_path/'native').exists() else ())
            self.last={'build_validation':receipt}
    validator=RealValidator();calls=[]
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
        if title=='NativeComponentMetadata':return json.dumps(metadata(NativeComponentBundle))
        if title=='NativeComponentSemantics':return json.dumps(dict(contracts={'component':dict(api_types=[PKG+'.Formatter'])}))
        if title=='MetadataChecklistBatch':
            return json.dumps(dict(task_revision=req['task_revision'],production_revision=req['production_revision'],batch_id=req['batch_id'],
                entries=[dict(checklist_id=i['id'],status='implemented',locations=[dict(path=PATH,excerpt='return value;')]) for i in req['assigned_items']]))
        return NativeTestBundle(files=[dict(path=TEST_PATH,content='package '+PKG+'''; public class FormatterTest {
            @org.junit.jupiter.api.Test public void preservesValue(){
                org.junit.jupiter.api.Assertions.assertEquals("value",new Formatter().format("value"));
            }}''')],coverage={'r':[TEST_PATH]}).model_dump_json()
    try:
        _,fingerprint=generate(conn,config,profile,'component_generation','unit','unused',payload,NativeComponentBundle,
            validator=validator,model_call=model)
        assert validator.last['build_validation']['test_count']==1
        assert calls==(['NativeImplementation','NativeComponentSemantics','MetadataChecklistBatch','NativeTestBundle'] if batched else ['NativeImplementation','NativeComponentMetadata','NativeTestBundle'])
        _,again=generate(conn,config,profile,'component_generation','unit','unused',payload,NativeComponentBundle,
            validator=validator,model_call=lambda *a:pytest.fail('Unchanged stages must revalidate without AI'))
        assert fingerprint==again
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='tests'").fetchone()[0]==1
    finally:conn.close()


def test_staged_operation_assembly_route_tests_and_warm_reuse(tmp_path):
    from tests.runtime.test_incremental_operation import setup,invoke,implementation
    from tests.runtime.test_scoped_native import actual_build
    values=setup(tmp_path,context_factory=actual_build)
    conn,config,profile,*_=values;profile.staged_unit_conversion=True
    calls=[]
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return NativeImplementation(files=implementation().files).model_dump_json()
        if title=='NativeUnitMetadata':
            value=implementation().model_dump(mode='json')
            value={k:v for k,v in value.items() if k not in {'files','dependencies','coverage'}}
            value['operation_contract'].pop('sources')
            return json.dumps(value)
        if title=='RouteTestPlan':
            return json.dumps(dict(scenarios=[dict(scenario_id=name,description='Execute '+name,
                inputs=['input='+str(value)],dependency_setup=[],expected_outcome='result='+str(result),
                covers=list(req['requirements']),routes=[dict(source='entry',outcome=outcome,target='end')])
                for name,value,result,outcome in [('success',1,1,'on0Do'),('failure',-1,-1,'onOtherDo')]]))
        assert title=='NativeTestBundle' and req['assembly_phase']=='single_route_test'
        result=1 if req['scenario']['scenario_id']=='success' else -1
        content=('package '+req['test_package']+'; public class '+req['test_class']+' { '
            '@org.junit.jupiter.api.Test public void preservesBranch(){org.junit.jupiter.api.Assertions.assertEquals('
            +str(result)+',new com.company.generated.Flow().execute('+str(result)+'));}}')
        return NativeTestBundle(files=[dict(path=req['expected_test_path'],content=content)]).model_dump_json()
    try:
        bundle,fingerprint=invoke(tmp_path,values,model)
        assert calls==['NativeImplementation','NativeUnitMetadata','RouteTestPlan','NativeTestBundle','NativeTestBundle']
        assert len(bundle.files)==3
        _,again=invoke(tmp_path,values,lambda *a:pytest.fail('Warm operation must reuse source-bound stages'))
        assert fingerprint==again
        assert conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category='service' AND status='accepted'").fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM staged_conversion_tasks WHERE stage='task_receipt'").fetchone()[0]==3
    finally:conn.close()


def test_missing_production_entry_returns_to_implementation_without_spending_metadata_repairs(monkeypatch):
    from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    conn,config=state();validator=Validator();calls=[]
    def validate_metadata(bundle):
        if validator.compiles==1:raise ImplementationInterfaceError('Required execute entry is absent')
    validator.validate_metadata=validate_metadata
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':
            if validator.compiles:assert 'Required execute entry' in json.dumps(req['implementation_feedback'])
            return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
        if title=='NativeComponentMetadata':return json.dumps(metadata(NativeComponentBundle))
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)],coverage={'r':[TEST_PATH]}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',max_agent_task_retries=2),
            'component_generation','entry','',request('configured_step'),NativeComponentBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeComponentMetadata','NativeImplementation','NativeComponentMetadata','NativeTestBundle']
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='metadata'").fetchone()[0]==2
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='implementation'").fetchone()[0]==2
    finally:conn.close()


def test_missing_compiled_step_entry_is_corrected_before_metadata_call(monkeypatch):
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    conn,config=state();validator=Validator();calls=[];payload=request('configured_step')
    payload['configured_unit']={'operation_calls':[]}
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':
            code=CODE if validator.compiles==0 else CODE.replace('public String format','public int execute(){return 0;} public String format')
            return NativeImplementation(files=[dict(path=PATH,content=code)]).model_dump_json()
        if title=='NativeComponentMetadata':return json.dumps(metadata(NativeComponentBundle))
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)],coverage={'r':[TEST_PATH]}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',max_agent_task_retries=2),
            'component_generation','entry','',payload,NativeComponentBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeImplementation','NativeComponentMetadata','NativeTestBundle']
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='metadata'").fetchone()[0]==1
    finally:conn.close()


def test_settings_binding_is_repaired_before_tests_and_kept_in_the_returned_bundle(monkeypatch):
    from runtime.behavior_conversion.failure_routing import AdapterRepairRequired
    from models.native_verification_binding import NativeVerificationBinding
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *args:None)
    conn,config=state();validator=Validator();calls=[];payload=request('format_composition')
    payload['sources'][0]['content']='package original; public class Formatter { public String format(String value){return value;} }'
    binding=NativeVerificationBinding.model_validate(metadata(NativeFormatComponentBundle)['verification_binding'])
    repaired=binding.model_copy(update={'output':'none'})
    ready=[]
    def prepare(bundle):
        if bundle.verification_binding.output!='none':raise AdapterRepairRequired({'stage':'binding_preparation'})
        ready.append(True)
    validator.validate_metadata=prepare
    monkeypatch.setattr('runtime.behavior_conversion.executable_adapters.resolve_adapter',lambda *args,**kwargs:repaired)
    def model(prompt,encoded):
        req=json.loads(encoded);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return NativeImplementation(files=[dict(path=PATH,content=CODE)]).model_dump_json()
        if title=='NativeFormatComponentDetails':return json.dumps({'component_details':{},'verification_binding':binding.model_dump(mode='json')})
        assert title=='NativeTestBundle' and ready
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)],coverage={'r':[TEST_PATH]}).model_dump_json()
    try:
        result,_=generate(conn,config,PipelineConfiguration(model_provider='mock',executable_verification={'mode':'executable_boundary_v1'}),
            'component_generation','unit','',payload,NativeFormatComponentBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeFormatComponentDetails','NativeTestBundle']
        assert result.verification_binding.output=='none'
        assert conn.execute("select status from staged_conversion_tasks where stage='implementation_ready'").fetchone()[0]=='retained'
    finally:conn.close()
