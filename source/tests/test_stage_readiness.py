"""Fail stage preparation before tests, and retain build readiness before comparison."""
from types import SimpleNamespace
import json
import pytest
from models.native_implementation import NativeImplementation
from models.native_unit_bundle import NativeUnitBundle
from models.pipeline_configuration import PipelineConfiguration
from models.native_unit_validation import NativeUnitValidation
from runtime.behavior_conversion.settings_readiness import prepare_settings
from runtime.behavior_conversion.stage_readiness import prepare_metadata,testing_gate as readiness_testing_gate,record_test_build
from runtime.behavior_conversion.failure_routing import AdapterRepairRequired,stage_error
from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete,VerificationFailure
from tools.state_store_tools import staged_conversion_state as state
from tools.component_inventory_tools.identity import stable_id
from tests.runtime.test_behavior_conversion import state as database

OWNER='com.company.generated.Ready'
SETTINGS='com.company.generated.Settings'
TARGET='legacy.Settings.configure'


def candidate():
    return NativeUnitBundle(files=[dict(path='src/main/java/com/company/generated/Ready.java',
        content='package com.company.generated; public class Ready { public String format(){return "";} }'),
        dict(path='src/main/java/com/company/generated/Settings.java',
        content='package com.company.generated; public class Settings { public static void configure(java.util.Set<String> values){} }')],
        unit_contract=dict(unit_id='u',apis=[dict(type_name=OWNER,method_signatures=['public String format()'])],
            requirements={'behavior':'Preserve'},evidence_ids=['source']),verification_binding=dict(owner_type=OWNER,method_name='format'))


def inventory(settings=True):
    types={OWNER:dict(methods=[dict(name='format',returns='java.lang.String',parameters=[],static='false')],
                      constructors=[dict(parameters=[])])}
    if settings:types[SETTINGS]=dict(methods=[dict(name='configure',returns='void',parameters=[dict(type='java.util.Set')],static='true')],constructors=[])
    return dict(types=types,apis=[],original_methods=[dict(target=TARGET,parameters=['java.util.Set'])])


@pytest.mark.parametrize('native_api,binding,expected',[
    (False,False,ImplementationInterfaceError), (True,False,AdapterRepairRequired), (True,True,None)])
def test_settings_preparation_distinguishes_missing_code_from_missing_wiring(monkeypatch,native_api,binding,expected):
    output=candidate()
    if binding:output.verification_binding.settings_bindings={TARGET:{'class':SETTINGS,'method':'configure'}}
    unit=dict(kind='response_format',effective_configuration={'tag':'Root'})
    controls=[dict(target=TARGET,arity=1)]
    generated=[]
    def cases(*args,**kwargs):
        generated.append(True)
        return [SimpleNamespace(model_dump=lambda **kwargs:{'case_id':'a'})]
    monkeypatch.setattr('runtime.behavior_conversion.settings_readiness.controlled_cases',cases)
    if expected:
        with pytest.raises(expected):prepare_settings(unit,None,output,controls,inventory=inventory(native_api))
        assert not generated
    else:
        result=prepare_settings(unit,None,output,controls,inventory=inventory(native_api))
        assert result['case_count']==1 and result['settings_targets']==[TARGET]


def task():
    conn,config=database()
    return SimpleNamespace(conn=conn,config=config,identity='u',revision='r',profile=PipelineConfiguration(),fresh=lambda:None)


def compile_proof(tasks,production):
    proof=dict(production_hash=stable_id(production.model_dump(mode='json')),validation={'build_passed':True})
    state.retain(tasks.conn,tasks.config.run_id,'u','r','compile',proof,stable_id(proof))


def test_binding_repairs_finish_before_readiness_without_production_or_test_calls(monkeypatch):
    tasks=task();bundle=candidate();production=NativeImplementation(files=bundle.files);compile_proof(tasks,production)
    events=[];original=production.model_dump_json()
    def check(output):
        events.append('prepare')
        if not output.verification_binding.settings_bindings:raise AdapterRepairRequired({'stage':'binding_preparation'})
    def repair(*args,**kwargs):
        events.append('adapter')
        return bundle.verification_binding.model_copy(update={'settings_bindings':{TARGET:{'class':SETTINGS,'method':'configure'}}})
    monkeypatch.setattr('runtime.behavior_conversion.executable_adapters.resolve_adapter',repair)
    try:
        prepare_metadata(tasks,{},production,inventory(),bundle,check)
        assert events==['prepare','adapter','prepare']
        assert original==production.model_dump_json()
        assert state.read(tasks.conn,tasks.config.run_id,'u','r','implementation_ready')['status']=='retained'
        assert tasks.conn.execute('select count(*) from staged_conversion_attempts').fetchone()[0]==0
    finally:tasks.conn.close()


@pytest.mark.parametrize('changed',['production','binding'])
def test_uncompiled_or_changed_candidate_cannot_advance_to_tests(changed):
    tasks=task();bundle=candidate();production=NativeImplementation(files=bundle.files)
    try:
        with pytest.raises(VerificationIncomplete,match='compile evidence'):
            prepare_metadata(tasks,{},production,inventory(),bundle,lambda _:pytest.fail('Unchecked production reached binding'))
        compile_proof(tasks,production)
        prepare_metadata(tasks,{},production,inventory(),bundle,lambda _:None)
        if changed=='production':bundle.files[0].content+='\n// changed'
        else:bundle.verification_binding.output='none'
        with pytest.raises(VerificationIncomplete,match='must be ready'):
            with readiness_testing_gate(tasks,bundle):pytest.fail('Stale code entered test execution')
    finally:tasks.conn.close()


def test_test_readiness_is_recorded_after_junit_before_comparison():
    tasks=task();bundle=candidate();production=NativeImplementation(files=bundle.files);compile_proof(tasks,production)
    try:
        prepare_metadata(tasks,{},production,inventory(),bundle,lambda _:None)
        from models.native_unit_bundle import NativeSourceFile
        bundle.files.append(NativeSourceFile(path='src/test/java/com/company/generated/ReadyTest.java',
            content='package com.company.generated; public class ReadyTest {}'))
        validation=NativeUnitValidation(build_passed=True,tests_passed=True,test_count=1,executed_test_classes=['ReadyTest'])
        with readiness_testing_gate(tasks,bundle):
            assert state.read(tasks.conn,tasks.config.run_id,'u','r','tests_ready')['status']!='retained'
            record_test_build(validation,{f.path:f.content for f in bundle.files},[])
            proof=state.read(tasks.conn,tasks.config.run_id,'u','r','tests_ready')
            assert proof['status']=='retained' and json.loads(proof['artifact_json'])['acceptance'] is False
        state.invalidate_readiness(tasks.conn,tasks.config.run_id,'u','r','binding')
        assert state.read(tasks.conn,tasks.config.run_id,'u','r','tests_ready')['status']=='stale'
        assert state.read(tasks.conn,tasks.config.run_id,'u','r','implementation_ready')['status']=='stale'
    finally:tasks.conn.close()


def test_settings_failure_never_returns_to_test_generation():
    error=VerificationFailure(dict(stage='cases',expected_settings=[dict(target=TARGET,arity=1)]))
    assert isinstance(stage_error(error,'tests'),AdapterRepairRequired)


def test_tests_must_call_the_prepared_native_settings_api():
    from runtime.behavior_conversion.native_test_scope import validate_test_scope
    scope=dict(owner_type=OWNER,method_name='format',opposite_methods=['unformat'],
               settings_bindings={TARGET:{'class':SETTINGS,'method':'configure'}})
    with pytest.raises(ValueError,match='native runtime settings'):
        validate_test_scope({'calls':[]},scope)
    validate_test_scope({'calls':[dict(receiver_type=SETTINGS,method='configure')]},scope)


def test_failed_junit_does_not_publish_test_readiness():
    tasks=task();bundle=candidate();production=NativeImplementation(files=bundle.files);compile_proof(tasks,production)
    try:
        prepare_metadata(tasks,{},production,inventory(),bundle,lambda _:None)
        from models.native_unit_bundle import NativeSourceFile
        bundle.files.append(NativeSourceFile(path='src/test/java/com/company/generated/ReadyTest.java',content='test source'))
        with readiness_testing_gate(tasks,bundle):
            with pytest.raises(VerificationIncomplete,match='passing JUnit'):
                record_test_build(NativeUnitValidation(build_passed=True,tests_passed=False),
                    {f.path:f.content for f in bundle.files},[])
        assert state.read(tasks.conn,tasks.config.run_id,'u','r','tests_ready')['status']!='retained'
    finally:tasks.conn.close()


def test_build_callback_cannot_compare_before_test_readiness(tmp_path):
    from runtime.behavior_conversion.bundle_output import accept_bundle
    from tests.runtime.test_behavior_conversion import factory,Verifier
    from models.native_unit_bundle import NativeSourceFile
    tasks=task();bundle=candidate();production=NativeImplementation(files=bundle.files);compile_proof(tasks,production)
    observed=[]
    try:
        prepare_metadata(tasks,{},production,inventory(),bundle,lambda _:None)
        bundle.files.append(NativeSourceFile(path='src/test/java/com/company/generated/ReadyTest.java',
            content='package com.company.generated; public class ReadyTest {}'))
        def compare(*args):
            observed.append(state.read(tasks.conn,tasks.config.run_id,'u','r','tests_ready')['status'])
        with readiness_testing_gate(tasks,bundle):
            accept_bundle(tmp_path/'project',{f.path:f.content for f in bundle.files},factory(Verifier()),
                tasks.profile,[],required_tests=[bundle.files[-1].path],pre_publish=compare)
        assert observed==['retained']
    finally:tasks.conn.close()
