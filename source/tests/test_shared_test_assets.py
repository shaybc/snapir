"""Immutable fixture references, separate suites and concrete failure modes."""
import json
from types import SimpleNamespace
import pytest
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from models.pipeline_configuration import PipelineConfiguration
from models.native_unit_bundle import NativeSourceFile
from runtime.test_assets.references import resolve
from runtime.test_assets.store import publish,load
from runtime.test_assets.validation import validate_bank,validate_suite
from runtime.test_assets.materialization import comparison_plan
from runtime.test_assets.junit_support import check_execution
from tools.conversion_tools.scoped_reuse.fingerprints import digest,conversion_policy


def fixtures():
    return SharedFixtureBank(fixtures={'record':dict(value={'flag':True,'rows':[{'name':'one'}],'nothing':None}),
        'xml':dict(kind='xml',value='\ufeff<x>\r\n text </x>'),
        'alias':dict(value={'$fixture':'record','pointer':'/rows'})})


def entry():
    return dict(owner_type='nativecode.Format',method_name='format',arguments=[dict(type_name='java.lang.Boolean',source='fixture',key='flag')])


def suites():
    junit=JunitScenarioSuite(scenarios=[dict(scenario_id='boolean_only',purpose='Small boolean method',native_entry=entry(),
        inputs={'flag':dict(fixture_id='record',pointer='/flag')},assertions=['The true flag produces true text'])])
    comparison=ComparisonScenarioSuite(scenarios=[dict(scenario_id='whole_format',purpose='Whole configured format',direction='format',
        native_entry=entry(),inputs={'flag':dict(fixture_id='record',pointer='/flag')},
        composer_context={'Flag':dict(fixture_id='record',pointer='/flag')})])
    return junit,comparison


def test_shared_data_separate_scenarios_and_fresh_copies():
    bank=fixtures();junit,comparison=suites()
    validate_bank(bank,[],10000);validate_suite(junit,bank,128);validate_suite(comparison,bank,64,direction='format')
    a=resolve(bank,dict(fixture_id='alias'));a[0]['name']='changed'
    assert resolve(bank,dict(fixture_id='alias'))==[{'name':'one'}]
    assert junit.scenarios[0].scenario_id!=comparison.scenarios[0].scenario_id
    assert resolve(bank,dict(fixture_id='xml'))=='\ufeff<x>\r\n text </x>'
    assert resolve(bank,dict(fixture_id='record',pointer='/nothing')) is None
    with pytest.raises(ValueError,match='Missing fixture pointer'):resolve(bank,dict(fixture_id='record',pointer='/absent'))


def test_missing_cyclic_and_malformed_references_fail():
    bank=fixtures()
    with pytest.raises(ValueError,match='Missing fixture'):resolve(bank,dict(fixture_id='missing'))
    bank.fixtures['alias'].value={'$fixture':'alias'}
    with pytest.raises(ValueError,match='Cyclic'):validate_bank(bank,[],10000)
    bank.fixtures['alias'].value={'$fixture':'record','compute':'ignore'}
    with pytest.raises(ValueError,match='Malformed'):validate_bank(bank,[],10000)


def test_immutable_manifests_detect_tampering_and_source_changes(tmp_path):
    bank=fixtures();junit,comparison=suites()
    root,m=publish(tmp_path,'component',{'source':'a'},bank,junit,comparison);h=digest(m.model_dump(mode='json'))
    assert publish(tmp_path,'component',{'source':'a'},bank,junit,comparison)[0]==root
    other,_=publish(tmp_path,'component',{'source':'b'},bank,junit,comparison)
    assert other!=root and root.exists()
    _,documents=load(root,h)
    assert documents['validation.json']['execution_status']=='not_run'
    (root/'fixtures.json').write_text('{}')
    with pytest.raises(ValueError,match='changed'):load(root,h)
    with pytest.raises(ValueError,match='changed'):publish(tmp_path,'component',{'source':'a'},bank,junit,comparison)


def test_explicit_comparison_scenarios_do_not_expand_and_keep_limit():
    from runtime.format_comparison.cases import expand_fixtures
    bank=fixtures();_,comparison=suites()
    source=NativeSourceFile(path='src/main/java/nativecode/Format.java',content='package nativecode;public class Format {}')
    plan=comparison_plan('sample',{'kind':'response_format','sources':[],'effective_configuration':{}},[source],bank,comparison,'hash')
    settings=PipelineConfiguration().format_comparison
    assert len(expand_fixtures(plan,settings))==1 and plan.cases[0].test_assets['inputs']=={'flag':True}
    comparison.scenarios*=65
    with pytest.raises(ValueError,match='limit'):validate_suite(comparison,bank,64)


def test_wrong_direction_and_fabricated_native_owner_rejected():
    bank=fixtures();_,comparison=suites()
    with pytest.raises(ValueError,match='unrequested'):validate_suite(comparison,bank,64,direction='unformat')
    comparison.scenarios[0].native_entry.owner_type='java.lang.System'
    sources=[NativeSourceFile(path='src/main/java/nativecode/Format.java',content='package nativecode;public class Format {}')]
    with pytest.raises(ValueError,match='actual supplied'):validate_suite(comparison,bank,64,native_sources=sources)


def test_jdbc_contract_does_not_invent_rows_or_operations():
    bank=SharedFixtureBank(fixtures={'db':dict(kind='database',value={'queries':[dict(sql='SELECT V FROM T WHERE K = ?',parameters=['k'],columns=['V'],rows=[[None]])]})})
    validate_bank(bank,[],10000)
    bank.fixtures['db'].value['queries'][0]['rows']=[[1,2]]
    with pytest.raises(ValueError,match='width'):validate_bank(bank,[],10000)
    bank.fixtures['db'].value={'connect_to':'production'}
    with pytest.raises(ValueError,match='prepared queries'):validate_bank(bank,[],10000)


def test_format_resources_require_explicit_setup_on_both_sides():
    bank=SharedFixtureBank(fixtures={'database':dict(kind='database',value={'queries':[]})})
    suite=ComparisonScenarioSuite(scenarios=[dict(scenario_id='resource_setup',purpose='Both consumers receive the fixture',direction='format',
        native_entry=dict(owner_type='nativecode.Format',method_name='format',arguments=[dict(type_name='nativecode.Model',source='object',
            properties={'assignResource':dict(type_name='java.sql.Connection',source='resource',key='arbitrary_resource')})]),
        resources={'arbitrary_resource':dict(fixture_id='database')})])
    with pytest.raises(ValueError,match='missing Composer resource attachment'):
        validate_suite(suite,bank,64)
    scenario=suite.scenarios[0]
    scenario.composer_resource_setters={'attachResource':'arbitrary_resource'}
    validate_suite(suite,bank,64)
    scenario.native_entry.arguments=[]
    with pytest.raises(ValueError,match='missing native resource recipes'):
        validate_suite(suite,bank,64)
    scenario.direction='step_execute'
    validate_suite(suite,bank,64)  # Operation-step policy is intentionally unchanged.


def test_materialization_rejects_unattached_retained_format_resources():
    bank=SharedFixtureBank(fixtures={'database':dict(kind='database',value={'queries':[]})})
    suite=ComparisonScenarioSuite(scenarios=[dict(scenario_id='retained',purpose='Reject incomplete saved setup',direction='unformat',
        native_entry=entry(),resources={'pool':dict(fixture_id='database')})])
    source=NativeSourceFile(path='src/main/java/nativecode/Format.java',content='package nativecode;public class Format {}')
    with pytest.raises(ValueError,match='Incomplete mock resource setup'):
        comparison_plan('retained',{'kind':'request_unformat'},[source],bank,suite,'hash')


def test_query_parameters_reference_shared_inputs_with_exact_case():
    bank=SharedFixtureBank(fixtures={'input':dict(value={'Identifier':'key-17'}),
        'database':dict(kind='database',value={'queries':[dict(sql='SELECT V FROM T WHERE K = ?',
            parameters=[{'$fixture':'input','pointer':'/Identifier'}],columns=['V'],rows=[])]})})
    validate_bank(bank,[],10000)
    assert resolve(bank,dict(fixture_id='database'))['queries'][0]['parameters']==['key-17']
    assert resolve(bank,dict(fixture_id='input'))=={'Identifier':'key-17'}


def test_original_configuration_xml_citations_keep_their_supplied_identity():
    xml='<opStep id="Sample" Limit="17" />'
    unit=dict(source_definition_id='definition-1',occurrence_id='occurrence-1',configuration_xml=xml+'\n',
        effective_configuration={'attributes':{'Limit':'17'}})
    citation=dict(source_identity='definition-1',excerpt=xml)
    bank=SharedFixtureBank(fixtures={'input':dict(value='17',origin='source_backed',citations=[citation])})
    validate_bank(bank,[],10000,unit=unit)
    suite=JunitScenarioSuite(scenarios=[dict(scenario_id='configured',purpose='Use exact configuration',native_entry=entry(),
        inputs={'flag':dict(fixture_id='input')},assertions=['Uses the configured limit'],assertion_citations=[citation])])
    validate_suite(suite,bank,64,unit=unit)
    suite.scenarios[0].assertion_citations[0].source_identity='occurrence-1'
    validate_suite(suite,bank,64,unit=unit)
    suite.scenarios[0].assertion_citations[0].excerpt='<opStep id="Sample" Limit="18" />'
    with pytest.raises(ValueError,match='absent from supplied original evidence'):validate_suite(suite,bank,64,unit=unit)
    bank.fixtures['input'].citations[0].source_identity='unknown'
    with pytest.raises(ValueError,match='absent from supplied original evidence'):validate_bank(bank,[],10000,unit=unit)


def test_native_dto_fixture_requires_explicit_construction_without_implicit_conversion():
    bank=SharedFixtureBank(fixtures={'data':dict(value={}), 'nil':dict(value=None)})
    suite=JunitScenarioSuite(scenarios=[dict(scenario_id='dto',purpose='Construct the declared DTO',
        native_entry=dict(owner_type='nativecode.Sample',method_name='run',arguments=[dict(type_name='nativecode.Record',source='fixture',key='value')]),
        inputs={'value':dict(fixture_id='data')},assertions=['Uses a constructed DTO'])])
    files=[NativeSourceFile(path='src/main/java/nativecode/Sample.java',content='package nativecode;public class Sample {public void run(Record value){}}'),
        NativeSourceFile(path='src/main/java/nativecode/Record.java',content='package nativecode;public class Record {}')]
    with pytest.raises(ValueError,match='requires source=object'):
        validate_suite(suite,bank,64,native_sources=files)
    suite.scenarios[0].native_entry.arguments[0].source='object'
    suite.scenarios[0].native_entry.arguments[0].key=None
    validate_suite(suite,bank,64,native_sources=files)
    suite.scenarios[0].native_entry.arguments[0].source='fixture'
    suite.scenarios[0].native_entry.arguments[0].key='value'
    suite.scenarios[0].inputs['value'].fixture_id='nil'
    validate_suite(suite,bank,64,native_sources=files)


def test_opt_in_policy_keeps_existing_profile_fingerprint():
    old=PipelineConfiguration();baseline=conversion_policy(old)
    same=old.model_copy(deep=True);same.test_preparation.request_chars=800000
    assert conversion_policy(same)==baseline
    same.test_preparation.mode='ai_shared_fixtures_v1'
    assert conversion_policy(same)!=baseline


def test_junit_receipt_is_required_in_addition_to_surefire(tmp_path):
    reports=tmp_path/'target/surefire-reports';reports.mkdir(parents=True)
    (reports/'TEST-test.xml').write_text('<testsuite><testcase classname="example.Test" name="checks"/></testsuite>')
    tests=SimpleNamespace(scenario_methods={'scenario':'example.Test#checks'},fixture_manifest_hash='hash')
    with pytest.raises(ValueError,match='did not execute their fixture'):check_execution(tmp_path,tests)
    (tmp_path/'target/shared-fixture-executions.jsonl').write_text(json.dumps(dict(scenario_id='scenario',manifest_hash='hash',callers=['example.Test#checks']))+'\n')
    check_execution(tmp_path,tests)
    tests.fixture_manifest_hash='changed'
    with pytest.raises(ValueError,match='did not execute their fixture'):check_execution(tmp_path,tests)
    tests.fixture_manifest_hash='hash'
    (reports/'TEST-test.xml').write_text('<testsuite><testcase classname="example.Test" name="checks"/><testcase classname="example.Test" name="unregistered"/></testsuite>')
    with pytest.raises(ValueError,match='lack shared-fixture scenario'):check_execution(tmp_path,tests)


def test_service_mock_cannot_replace_undeclared_business_method():
    bank=fixtures();_,comparison=suites();comparison.native_external_bindings={'nativecode.Format.format(java.lang.Boolean)':'invented'}
    with pytest.raises(ValueError,match='business methods cannot be stubbed'):validate_suite(comparison,bank,64)


def test_junit_rejects_ignored_projection_and_missing_setter_input():
    bank=fixtures();junit,_=suites()
    junit.scenarios[0].native_entry.output_getters=['getValue']
    with pytest.raises(ValueError,match='raw result'):validate_suite(junit,bank,128)
    junit.scenarios[0].native_entry.output_getters=[]
    from models.native_boundary_value import NativeBoundaryValue
    junit.scenarios[0].native_entry.configuration_setters={'setTag':NativeBoundaryValue(type_name='java.lang.String',source='configuration',key='tag')}
    with pytest.raises(ValueError,match='Missing JUnit configuration'):validate_suite(junit,bank,128)


def test_constructor_scenario_and_exact_public_api_selection():
    from models.native_verification_binding import NativeVerificationBinding
    from runtime.test_assets.api_contracts import validate_invocation
    binding=NativeVerificationBinding(owner_type='nativecode.Format',method_name='<init>',
        constructor_arguments=[dict(type_name='java.lang.Boolean',source='fixture',key='flag')])
    junit=JunitScenarioSuite(scenarios=[dict(scenario_id='construct',purpose='Constructor configuration',entry_kind='constructor',
        native_entry=binding,inputs={'flag':dict(fixture_id='record',pointer='/flag')},assertions=['Retains flag'])])
    sources=[NativeSourceFile(path='src/main/java/nativecode/Format.java',content='package nativecode;public class Format {public Format(Boolean flag){}}')]
    inventory=dict(types={'nativecode.Format':dict(constructors=[dict(parameters=[dict(type='java.lang.Boolean')])],
        methods=[dict(name='format',static='false',parameters=[dict(type='java.lang.String')])])})
    validate_suite(junit,fixtures(),128,native_sources=sources,api_inventory=inventory)
    from models.native_boundary_value import NativeBoundaryValue
    binding.method_name='format';binding.arguments=[NativeBoundaryValue(type_name='java.lang.Boolean',source='fixture',key='flag')]
    with pytest.raises(ValueError,match='exact parsed public signature'):validate_invocation(binding,inventory)
    inventory['types']['nativecode.Format']['constructors']=[]
    binding.constructor_arguments=[]
    with pytest.raises(ValueError,match='exact parsed public signature'):validate_invocation(binding,inventory,constructor_entry=True)


def test_explicit_fixture_resource_collections_retain_existing_limits():
    from models.format_comparison_case import FormatComparisonCase
    from runtime.test_assets.limits import validate_case_limits
    profile=PipelineConfiguration();profile.executable_verification.max_collection_items=2
    case=FormatComparisonCase(case_id='rows',binding_id='format',test_assets={'resources':{'db':{'queries':[{'rows':[[1],[2],[3]]}]}}})
    with pytest.raises(ValueError,match='collection'):validate_case_limits([case],profile)


def test_shared_compilation_failure_retains_root_cause_for_later_cases(monkeypatch,tmp_path):
    from models.boundary_harness_binding import BoundaryHarnessBinding
    from models.native_verification_binding import NativeVerificationBinding
    from runtime.format_comparison.execution import execute_pair
    from models.format_comparison_case import FormatComparisonCase
    plan=SimpleNamespace(native_sources=[],native_classpath=[],native_external_bindings={},
        original_framework=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'))
    binding=NativeVerificationBinding(owner_type='nativecode.Format',method_name='format')
    case=FormatComparisonCase(case_id='first',binding_id='format')
    monkeypatch.setattr('runtime.format_comparison.execution.analyze_unit',lambda *a,**k:None)
    calls=[]
    def compile_failed(*args,**kwargs):
        calls.append(args[3]);args[3].mkdir();raise ValueError('Unsupported codec call')
    monkeypatch.setattr('runtime.format_comparison.execution.compile_boundary_side',compile_failed)
    compiled={};boundaries={};failures={};settings=PipelineConfiguration().format_comparison
    for identity in ['first','second']:
        case.case_id=identity
        with pytest.raises(ValueError,match='Unsupported codec call'):
            execute_pair(plan,{},binding,case,tmp_path,tmp_path/'tool.jar',settings,compiled,boundaries,compilation_failures=failures)
    assert len(calls)==1 and not compiled


def test_harness_dependency_shadowing_is_rejected(tmp_path):
    from zipfile import ZipFile
    from runtime.test_assets.runtime_dependencies import verify_runtime_dependencies
    a=tmp_path/'harness.jar';b=tmp_path/'native.jar'
    with ZipFile(a,'w') as z:z.writestr('library/Api.class',b'one')
    with ZipFile(b,'w') as z:z.writestr('library/Api.class',b'two')
    with pytest.raises(ValueError,match='dependency conflict'):verify_runtime_dependencies(a,[b])


def test_explicit_exception_observations_can_match_without_hiding_setup_failures():
    from models.boundary_observation import BoundaryObservation
    from runtime.format_comparison.reporting import compare_case
    left=BoundaryObservation(case_id='exception',status='completed',exception={'type':'java.lang.IllegalArgumentException'})
    right=left.model_copy(deep=True);settings=PipelineConfiguration().format_comparison
    assert compare_case(left,right,'format',settings)['status']=='matched'
    assert compare_case(left,right,'format',settings,observe_context_keys=[])['status']=='matched'
    right.status='verification_incomplete'
    assert compare_case(left,right,'format',settings,observe_context_keys=[])['status']=='comparison_unavailable'
