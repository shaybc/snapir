"""Exercise explicit framework ownership, saved-run updates, and source-less binary entry analysis."""
import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile
import pytest
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from tools.framework_boundaries.inventory import scan, framework_scope, owner, current
from tools.framework_boundaries.run_update import update_run
from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy
from test_behavior_verification_boundaries import boundary_tool, unit, source, prepared
from test_boundary_project_classpath import archive
from test_component_formats import format_case


@pytest.fixture(scope='module', autouse=True)
def selected_jdk():
    with java_scope(PipelineConfiguration(java_version=25)): yield


def binary(path, names):
    with ZipFile(path, 'w') as jar:
        for name in names: jar.writestr(name + '.class', b'not executed')
    return path


def test_inventory_is_exact_nested_multi_release_and_scoped(tmp_path):
    first = binary(tmp_path/'one.jar', ['vendor/Base', 'vendor/Base$Nested', 'META-INF/versions/21/vendor/New', 'module-info'])
    second = binary(tmp_path/'two.jar', ['other/Type'])
    assert set(scan([first, second])) == {'vendor.Base', 'vendor.Base$Nested', 'vendor.New', 'other.Type'}
    with framework_scope([first, second]):
        assert owner('vendor.Base.Nested')
        assert owner('vendor.NotFramework') is None
    assert not current()
    with pytest.raises(ValueError, match='Conflicting'):
        scan([first, binary(tmp_path/'conflict.jar', ['vendor/Base'])])


def test_saved_run_update_preserves_profile_evidence_and_progress(tmp_path):
    run = tmp_path/'saved-run'; (run/'state').mkdir(parents=True)
    profile = PipelineConfiguration(source_root='unchanged', framework_jars=[])
    (run/'state/profile.json').write_text(profile.model_dump_json())
    with sqlite3.connect(run/'state/migration.db') as conn:
        conn.execute('CREATE TABLE runs(run_id,status,current_phase)')
        conn.execute('INSERT INTO runs VALUES(?,?,?)', (run.name,'blocked','conversion_components_incomplete'))
        conn.execute('CREATE TABLE captured_evidence(value)'); conn.execute('INSERT INTO captured_evidence VALUES(?)', ('keep',))
    jar = binary(tmp_path/'framework.jar', ['vendor/Base'])
    config = tmp_path/'framework.yaml'; config.write_text('framework_jars: [framework.jar]')
    result = update_run(run, config)
    assert result.framework_jars == [str(jar.resolve())]
    assert update_run(run, config).framework_jars == result.framework_jars
    assert result.source_root == 'unchanged'
    assert conversion_policy(result) == conversion_policy(profile)
    with sqlite3.connect(run/'state/migration.db') as conn:
        assert conn.execute('SELECT value FROM captured_evidence').fetchone()[0] == 'keep'
        assert conn.execute('SELECT current_phase FROM runs').fetchone()[0] == 'conversion_components_incomplete'
        assert conn.execute('SELECT count(*) FROM framework_boundary_updates').fetchone()[0] == 1
    config.write_text('framework_jars: []\nsource_root: changed')
    with pytest.raises(ValueError, match='only framework_jars'): update_run(run, config)
    assert json.loads((run/'state/profile.json').read_text())['source_root'] == 'unchanged'


def test_missing_framework_source_preserves_application_parser_evidence(tmp_path, boundary_tool):
    jar = archive(tmp_path/'framework', {'vendor/Base.java': 'package vendor; public class Base { public int execute(){return 7;} }'})
    value = unit(sources=[source('work','package example; public class Work extends vendor.Base { public int business(){return 9;} }'),
        source('unrelated','package example; public class Unrelated { public int hidden(){return 100;} }')])
    from tools.behavior_verification.boundaries import build_boundary_report
    before = build_boundary_report(prepared(value), tool_jar=boundary_tool)
    assert before['counts']['identified'] == 0
    with framework_scope([jar]):
        report = build_boundary_report(prepared(value), tool_jar=boundary_tool)
    boundary = report['boundaries'][value['unit_id']]
    assert boundary['analysis_status'] == 'identified', boundary['issues']
    assert boundary['legacy_method'] is None
    assert boundary['framework_boundaries'][0]['signature'] == 'vendor.Base.execute()'
    assert any(node['signature'] == 'example.Work.business()' for node in boundary['reachable_slice']['nodes'])
    assert not any(node['declaring_class']=='example.Unrelated' for node in boundary['reachable_slice']['nodes'])
    assert boundary['parser_checklist']['status'] == 'extracted', boundary['parser_checklist']
    assert all(node['path_certainty']=='uncertain' for node in boundary['reachable_slice']['nodes'])


def test_source_override_remains_application_code(tmp_path, boundary_tool):
    jar = archive(tmp_path/'framework', {'vendor/Base.java': 'package vendor; public class Base { public int execute(){return 7;} }'})
    value = unit(sources=[source('work','package example; public class Work extends vendor.Base { public int execute(){return 9;} }')])
    from tools.behavior_verification.boundaries import build_boundary_report
    with framework_scope([jar]): report = build_boundary_report(prepared(value), tool_jar=boundary_tool)
    boundary = report['boundaries'][value['unit_id']]
    assert boundary['legacy_method']['declaring_class'] == 'example.Work'
    assert not boundary.get('framework_boundaries')


def test_comparison_executes_real_framework_jar_and_rejects_wrong_native_result(tmp_path, boundary_tool):
    from models.format_comparison_plan import FormatComparisonPlan
    from runtime.format_comparison.planning import original_unit
    from runtime.format_comparison.runner import run_comparison
    root = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace/WSBCC_XML/src'
    files = {'com/ibm/dse/base/' + name + '.java': next(root.rglob(name + '.java')).read_text() for name in ('Context', 'Tag')}
    files['vendor/Base.java'] = """package vendor; public abstract class Base {
        public void initializeFrom(com.ibm.dse.base.Tag tag){}
        public String format(com.ibm.dse.base.Context context){return "framework:" + formatField((String)context.getValueAt("value"));}
        protected abstract String formatField(String value);
    }"""
    jar = archive(tmp_path/'framework', files)
    value = original_unit([source('work', 'package example; public class Work extends vendor.Base { protected String formatField(String value){return value.toUpperCase(java.util.Locale.ROOT);} }')],
        dict(java_class='example.Work', attributes={}))
    native = 'package nativecode; public class Work { public static String format(String value){return "framework:"+value.toUpperCase(java.util.Locale.ROOT);} }'
    plan = FormatComparisonPlan(label='framework-wrapper', scope='basic', original_unit=value,
        native_sources=[dict(path='src/main/java/nativecode/Work.java', content=native)],
        entries={'write':dict(direction='format', binding=dict(owner_type='nativecode.Work',method_name='format',static_method=True,
            arguments=[dict(type_name='java.lang.String',source='context',key='value')]))},
        cases=[dict(case_id='normal',binding_id='write',initial_context={'value':'hello'})])
    profile = PipelineConfiguration(java_version=25, framework_jars=[str(jar)], format_comparison=dict(enabled=True,collect_facts=False))
    report = run_comparison(plan, profile, tmp_path/'comparison', tool=boundary_tool)
    assert report['counts'].get('matched') == 1, report
    assert report['cases'][0]['legacy']['output'] == 'framework:HELLO'
    wrong = plan.model_copy(deep=True)
    wrong.native_sources[0].content = native.replace('"framework:"+', '')
    result = run_comparison(wrong, profile, tmp_path/'wrong-comparison', tool=boundary_tool)
    assert result['counts'].get('matched', 0) == 0, result
    assert result['cases'][0]['legacy']['output'] == 'framework:HELLO'
    assert result['cases'][0]['native']['output'] == 'HELLO'


def test_component_request_reaches_generation_without_framework_source(tmp_path, boundary_tool):
    from tools.behavior_verification.boundaries import build_boundary_report
    from tools.conversion_tools.component_graph import build_component_plan
    from tools.conversion_tools.component_identity import component_group
    from runtime.component_conversion.requests import build_component_request
    jar = archive(tmp_path/'framework', {'vendor/Base.java':'package vendor; public class Base { public int execute(){return 7;} }'})
    text = 'package example; public class Work extends vendor.Base { public int business(){return 9;} }'
    path = tmp_path/'Work.java'; path.write_text(text)
    value = unit(sources=[source('work',text)])
    value.update(source_definition_id='step',occurrence_id='step',logical_id='Work')
    origin = dict(fqcn='example.Work',definition_id='work',source_file=str(path),source_hash=value['sources'][0]['content_hash'],
        status='verified_source',required_classes=['vendor.Base'])
    preparation = dict(operations={'BANK/Op':dict(status='prepared',units=[value],behavior_request=dict(java_origins=[origin]))})
    with framework_scope([jar]):
        plan = build_component_plan(preparation['operations'])
        assert not plan.issues, plan.issues
        report = build_boundary_report(preparation,tool_jar=boundary_tool,collect_checklists=False)
        component = next(key for key,node in plan.components.items() if node.label=='example.Work')
        profile = PipelineConfiguration(java_version=25,executable_verification=dict(mode='test_based_v1'))
        request, instruction = build_component_request(plan,component_group(plan,component),report,[],profile,
            check_budget=False,units={value['unit_id']:value})
    assert any(item.get('declaring_class')=='vendor.Base' for item in request['framework_boundaries'])
    assert [item['identity'] for item in request['sources']]==['work']
    assert 'do not generate framework classes' in instruction.lower()
    assert 'composer_behavior' not in request  # Existing encoding attaches the manual once.
    assert not request['retained_libraries']


def test_framework_format_uses_actual_unique_binary_signature(tmp_path, boundary_tool):
    files = {
        'vendor/Operation.java':'package vendor; public class Operation {}',
        'vendor/DataField.java':'package vendor; public class DataField {}',
        'vendor/Base.java':'package vendor; public class Base { public void unformat(String wire,Operation operation){} protected DataField unformatField(String wire,DataField field){return field;} }'}
    jar = archive(tmp_path/'framework', files)
    value = unit('request_unformat','example.Work',[source('work','package example; public class Work extends vendor.Base {}')])
    value.update(format_scope='basic',effective_configuration=dict(java_class='example.Work',attributes={}))
    from tools.behavior_verification.boundaries import build_boundary_report
    with framework_scope([jar]): report = build_boundary_report(prepared(value),tool_jar=boundary_tool)
    boundary = report['boundaries'][value['unit_id']]
    assert boundary['analysis_status']=='identified', boundary['issues']
    assert boundary['framework_boundaries'][0]['parameters']==['java.lang.String','vendor.Operation']
    assert boundary['legacy_method'] is None


def test_framework_ownership_does_not_approve_native_retention(tmp_path):
    from runtime.retained_libraries.catalog import record_libraries
    jar = binary(tmp_path/'framework.jar',['vendor/Base'])
    with framework_scope([jar]):
        assert record_libraries([dict(class_name='vendor.Base',library={'invalid':'must not be retained'})])==[]


def test_unreadable_update_keeps_saved_profile(tmp_path):
    run=tmp_path/'saved'; (run/'state').mkdir(parents=True)
    previous=PipelineConfiguration().model_dump_json()
    (run/'state/profile.json').write_text(previous)
    config=tmp_path/'framework.yaml';config.write_text('framework_jars: [absent.jar]')
    with pytest.raises(ValueError,match='existing archive'): update_run(run,config)
    assert (run/'state/profile.json').read_text()==previous


@pytest.mark.parametrize('code', [
    'package example; import vendor.Base; public class Work extends Base {}',
    'package example; public class Work extends vendor.Base {}',
    'package vendor; public class Base {}',
    'package example; import vendor.*; public class Work extends Base {}'])
def test_native_output_cannot_retain_or_shadow_framework(tmp_path, code):
    from models.native_unit_bundle import NativeSourceFile
    from tools.framework_boundaries.native_output import reject_framework_output
    jar=binary(tmp_path/'framework.jar',['vendor/Base'])
    with framework_scope([jar]), pytest.raises(ValueError, match='original framework'):
        reject_framework_output([NativeSourceFile(path='src/main/java/example/Work.java',content=code)])


def test_configured_framework_only_step_needs_no_fabricated_source(tmp_path, boundary_tool):
    from tools.behavior_verification.boundaries import build_boundary_report
    from tools.conversion_tools.component_graph import build_component_plan
    from tools.conversion_tools.component_identity import component_group
    from runtime.component_conversion.requests import build_component_request
    jar=archive(tmp_path/'framework',{'vendor/Base.java':'package vendor; public class Base { public int execute(){return 7;} }'})
    value=unit(name='vendor.Base');value['sources']=[]
    value.update(source_definition_id='step',occurrence_id='step',logical_id='ConfiguredWork')
    preparation=dict(operations={'BANK/Op':dict(status='prepared',units=[value],behavior_request=dict(java_origins=[]))})
    with framework_scope([jar]):
        plan=build_component_plan(preparation['operations'])
        report=build_boundary_report(preparation,tool_jar=boundary_tool)
        key=plan.unit_roots[value['unit_id']]
        request,_=build_component_request(plan,component_group(plan,key),report,[],PipelineConfiguration(java_version=25),
            check_budget=False,units={value['unit_id']:value})
    assert request['sources']==[]
    assert request['parser_checklist']==[]
    assert request['framework_boundaries']
    assert request['configured_unit']['resolved_implementation']=='vendor.Base'


def test_native_output_allows_framework_names_in_documentation(tmp_path):
    from models.native_unit_bundle import NativeSourceFile
    from tools.framework_boundaries.native_output import reject_framework_output
    jar=binary(tmp_path/'framework.jar',['vendor/Base'])
    with framework_scope([jar]):
        reject_framework_output([NativeSourceFile(path='src/main/java/example/Work.java',
            content='package example; /* replaces vendor.Base */ public class Work { String description="vendor.Base"; }')])


def test_framework_context_keeps_resolved_source_signature_for_static_validation(format_case, tmp_path):
    from test_component_formats import request_for, fixture_tree, candidate
    from models.native_format_component_bundle import NativeFormatComponentBundle
    from runtime.component_conversion.format_verification import format_bundle, session_for
    _,config,profile,_,_,boundaries,units=format_case
    _,request,_=request_for(format_case,'response')
    request,files=fixture_tree(request)
    native=NativeFormatComponentBundle.model_validate(candidate(request,dependencies=files))
    jar=archive(tmp_path/'framework',{'vendor/Runtime.java':'package vendor; public class Runtime {}'})
    with framework_scope([jar]):
        session=session_for(config,profile,units['response'],boundaries['boundaries']['response'])
        session.static(format_bundle(native,request,files))
    assert session.static_report.status=='mapping_valid',session.static_report.errors
