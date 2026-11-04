"""AI duties stay distinct; fixtures and scenario definitions cannot edit production."""
from types import SimpleNamespace
from models.pipeline_configuration import PipelineConfiguration
from models.native_implementation import NativeImplementation
from runtime.test_assets.preparation import prepare
from test_shared_test_assets import fixtures,suites


def test_three_independent_preparation_stages_share_fixtures(tmp_path):
    profile=PipelineConfiguration(test_preparation={'mode':'ai_shared_fixtures_v1'},format_comparison={'enabled':True})
    bank=fixtures();junit,comparisons=suites();calls=[]
    class Tasks:
        identity='component';config=SimpleNamespace(output_root=str(tmp_path))
        def ask(self,stage,request,prompt,schema,check,**kwargs):
            calls.append((stage,request))
            value={'fixture_catalog':bank,'junit_scenarios':junit,'comparison_scenarios':comparisons}[stage]
            check(value);return value
    tasks=Tasks();tasks.profile=profile
    production=NativeImplementation(files=[dict(path='src/main/java/nativecode/Format.java',content='package nativecode;public class Format {public String format(Boolean flag){return "x";}}')])
    payload=dict(configured_format=dict(kind='response_format'),sources=[])
    result=prepare(tasks,payload,production,dict(apis=[]))
    assert [c[0] for c in calls]==['fixture_catalog','junit_scenarios','comparison_scenarios']
    assert calls[1][1]['fixture_bank']==calls[2][1]['fixture_bank']
    assert calls[2][1]['comparison_case_limit']==64
    assert result['junit'].scenarios[0].scenario_id!=result['comparisons'].scenarios[0].scenario_id
    assert result['root'].startswith(str(tmp_path))
    dependency_path='src/main/java/nativecode/Dependency.java'
    first=prepare(tasks,payload,production,dict(apis=[]),[(dependency_path,'package nativecode;public class Dependency {public int value(){return 1;}}')])
    second=prepare(tasks,payload,production,dict(apis=[]),[(dependency_path,'package nativecode;public class Dependency {public int value(){return 2;}}')])
    assert first['root']!=second['root']


def test_opt_in_staged_pipeline_keeps_implementation_and_scenario_roles_separate(monkeypatch,tmp_path):
    """Flow-only validator; real fixture/JUnit execution is tested in test_shared_fixture_execution."""
    import json
    from runtime.behavior_conversion.generation import generate
    from runtime.java_toolchain import java_scope
    from models.native_unit_bundle import NativeUnitBundle
    from models.native_test_bundle import NativeTestBundle
    from test_staged_pipeline import request,Validator,CODE,PATH,PKG,TEST_PATH
    from tests.runtime.test_behavior_conversion import state
    from runtime.test_assets.preparation import current
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *args:None)
    monkeypatch.setattr('runtime.test_assets.junit_support.install_runtime',lambda profile:None)
    conn,config=state();config.output_root=str(tmp_path);calls=[]
    payload=request('response_format');payload['sources'][0]['content']='package original;public class Formatter {public String format(String value){return value;}}'
    from models.junit_test_scenario import JunitScenarioSuite
    from models.shared_test_fixture import SharedFixtureBank
    from models.comparison_test_scenario import ComparisonScenarioSuite
    bank=SharedFixtureBank(fixtures={'text':dict(value='hello')})
    binding=dict(owner_type=PKG+'.Formatter',method_name='format',arguments=[dict(type_name='java.lang.String',source='fixture',key='text')])
    suite=JunitScenarioSuite(scenarios=[dict(scenario_id='small',purpose='Native identity method',native_entry=binding,inputs={'text':dict(fixture_id='text')},assertions=['Returns hello'])])
    class Validate(Validator):
        def __call__(self,bundle,cached=False):
            assert current()['junit'].scenarios[0].scenario_id=='small'
            return super().__call__(bundle,cached)
    def model(prompt,encoded):
        data=json.loads(encoded);title=data['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return json.dumps(dict(files=[dict(path=PATH,content=CODE)]))
        if title=='SharedFixtureBank':return bank.model_dump_json()
        if title=='JunitScenarioSuite':return suite.model_dump_json()
        if title=='ComparisonScenarioSuite':return ComparisonScenarioSuite(unresolved=['Pilot fixtures not requested']).model_dump_json()
        if title=='NativeTestBundle':
            h=data['shared_fixture_manifest_hash']
            text='package '+PKG+';import il.co.dcd.verification.fixtures.FixtureStore;public class FormatterTest {public void check()throws Exception {FixtureStore.open("'+data['shared_fixture_root']+'","'+h+'").run("small");}}'
            return NativeTestBundle(files=[dict(path=TEST_PATH,content=text)],coverage={key:[TEST_PATH] for key in data['requirements']},fixture_manifest_hash=h,scenario_methods={'small':PKG+'.FormatterTest#check'}).model_dump_json()
        return json.dumps(dict(entry_type=PKG+'.Formatter'))
    profile=PipelineConfiguration(java_version=25,model_provider='mock',test_preparation={'mode':'ai_shared_fixtures_v1'},
        format_comparison={'enabled':True},executable_verification={'mode':'conversion_checklist_v1','experimental_disable_facts':True})
    try:
        with java_scope(profile):result,_=generate(conn,config,profile,'component_generation','unit','existing',payload,NativeUnitBundle,validator=Validate(),model_call=model)
        assert len(result.files)==2 and calls.count('NativeImplementation')==1
        assert all(name in calls for name in ['SharedFixtureBank','JunitScenarioSuite','ComparisonScenarioSuite','NativeTestBundle'])
    finally:conn.close()


def test_missing_fixture_feedback_returns_to_owning_preparation_stages(tmp_path):
    from models.shared_test_fixture import SharedFixtureBank
    from models.junit_test_scenario import JunitScenarioSuite
    bank=fixtures();junit,comparisons=suites();junit.unresolved=['Missing configured tag fixture']
    repaired_bank=bank.model_copy(deep=True);repaired_bank.fixtures['tag']=__import__('models.shared_test_fixture',fromlist=['SharedTestFixture']).SharedTestFixture(value='Flag')
    repaired_suite=junit.model_copy(deep=True);repaired_suite.unresolved=[];calls=[]
    class Tasks:
        identity='component';config=SimpleNamespace(output_root=str(tmp_path))
        profile=PipelineConfiguration(test_preparation={'mode':'ai_shared_fixtures_v1'},format_comparison={'enabled':True})
        def ask(self,stage,request,prompt,schema,check,**kwargs):
            calls.append(stage)
            if stage=='fixture_catalog':value=repaired_bank if 'preparation_feedback' in request else bank
            elif stage=='junit_scenarios':value=repaired_suite if 'preparation_feedback' in request else junit
            else:value=comparisons
            check(value);return value
    production=NativeImplementation(files=[dict(path='src/main/java/nativecode/Format.java',content='package nativecode;public class Format {}')])
    result=prepare(Tasks(),dict(kind='response_format',sources=[]),production,dict(apis=[]))
    assert calls==['fixture_catalog','junit_scenarios','fixture_catalog','junit_scenarios','comparison_scenarios']
    assert not result['junit'].unresolved and 'tag' in result['bank'].fixtures
