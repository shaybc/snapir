"""CF3 uses parser evidence and real Maven/JUnit fixtures, not live AI acceptance."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.native_component_bundle import NativeComponentBundle
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.component_identity import component_group
from tools.behavior_verification.boundaries import build_boundary_report
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.runs import upsert_run
from runtime.component_conversion.requests import build_component_request, basic_group
from runtime.component_conversion.scope import component_execution
from runtime.component_conversion.runner import convert_basic_components
from runtime.behavior_conversion.generation import generate
from test_component_graph import origin, step, operation
from test_behavior_verification_boundaries import boundary_tool
from test_scoped_vault_identity import scoped_mapper

PRIMITIVES = '''package example;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Set;
import java.util.Map;
import java.util.HashMap;
public class Primitives {
 public String string(String value) { return value == null ? "" : value; }
 public String date(Date value, String pattern) { return new SimpleDateFormat(pattern).format(value); }
 public String mandatory(String value) {
  if (value == null || value.isEmpty()) throw new IllegalArgumentException("Mandatory value is missing");
  return value;
 }
 public String zero(String value) { return value == null || value.isEmpty() ? "0" : value; }
 public Map<String,String> nil(String value, String channel, String application, Set<String> channels, Set<String> excluded) {
  Map<String,String> attributes = new HashMap<>();
  try {
   if (channels.contains(channel.toLowerCase()) && !excluded.contains(application.toLowerCase())) {
    if (value == null || value.length() == 0) attributes.put("xsi:nil", "true");
   }
  } catch (Exception exception) { }
  return attributes;
 }
 public int execute() {
  string(null); date(new Date(0), "yyyyMMdd");
  try { mandatory(null); } catch (IllegalArgumentException exception) { }
  zero(null); nil(null,"XML","bank",Set.of("xml"),Set.of()); return 0;
 }
}'''


@pytest.fixture
def component_case(tmp_path, boundary_tool, monkeypatch):
    folder = tmp_path / 'original'; folder.mkdir()
    originals = [origin('example.Work', ['example.Primitives'],
        'package example; public class Work { public int execute(){return new Primitives().execute();} }'),
        origin('example.Primitives', text=PRIMITIVES), origin('example.Unrelated')]
    for item, text in originals:
        path = folder / (item['fqcn'].rsplit('.', 1)[-1] + '.java')
        path.write_text(text, encoding='utf-8', newline='\n'); item['source_file'] = str(path)
    operations = {'XML/Flow': operation([step()], originals)}
    plan = build_component_plan(operations)
    preparation = dict(operations=operations, component_plan=plan.model_dump(mode='json'))
    boundaries = build_boundary_report(preparation, tool_jar=boundary_tool)
    assert boundaries['counts']['identified'] == 1, boundaries
    key = next(key for key, node in plan.components.items() if node.label == 'example.Primitives')
    group = component_group(plan, key)
    conn = get_connection(str(tmp_path / 'state.db')); create_all_tables(conn)
    config = SimpleNamespace(run_id='cf3-fixture', output_root=str(tmp_path / 'output'), source_root=str(folder))
    upsert_run(conn, run_id=config.run_id, run_mode='conversion')
    profile = PipelineConfiguration(source_root=str(folder), conversion_strategy='behavior_units',
        scoped_native_mode='component_first_v1', java_version=25, max_agent_task_retries=2)
    # This isolated fixture has no imported scoped vault. Real scoped checkpoints are exercised separately.
    monkeypatch.setattr('runtime.component_conversion.scope.validate_checkpoints', lambda *a: None)
    yield conn, config, profile, preparation, plan, group, boundaries
    conn.close()


def native_fixture(request, *, bad=False):
    """Deterministic candidate fixture derived from the supplied demo-like source, not AI output."""
    package = request['native_package']; key = next(iter(request['components']))
    main = PRIMITIVES.replace('package example;', 'package ' + package + ';')
    if bad: main = main.replace('return 0;', 'return missingVariable;')
    prefix = package.replace('.', '/')
    main_path = 'src/main/java/' + prefix + '/Primitives.java'
    test_path = 'src/test/java/' + prefix + '/PrimitivesTest.java'
    test = '''package PACKAGE;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.util.Set;
import java.util.Date;
public class PrimitivesTest {
 @Test public void stringAndDate() throws Exception {
  Primitives value = new Primitives();
  assertEquals("",value.string(null)); assertEquals(" ",value.string(" "));
  assertEquals("20261027",value.date(new java.text.SimpleDateFormat("yyyy-MM-dd").parse("2026-10-27"),"yyyyMMdd"));
  assertEquals("27/10/2026",value.date(new java.text.SimpleDateFormat("yyyy-MM-dd").parse("2026-10-27"),"dd/MM/yyyy"));
 }
 @Test public void mandatoryAndZero() {
  Primitives value = new Primitives();
  assertThrows(IllegalArgumentException.class,()->value.mandatory(null));
  assertThrows(IllegalArgumentException.class,()->value.mandatory("")); assertEquals(" ",value.mandatory(" "));
  assertEquals("0",value.zero(null)); assertEquals("0",value.zero("")); assertEquals(" ",value.zero(" "));
 }
 @Test public void nilRuntimeConditions() {
  Primitives value = new Primitives(); Set<String> channels = Set.of("xml");
  assertEquals("true",value.nil(null,"XML","bank",channels,Set.of()).get("xsi:nil"));
  assertEquals("true",value.nil("","XML","bank",channels,Set.of()).get("xsi:nil"));
  assertTrue(value.nil("text","XML","bank",channels,Set.of()).isEmpty());
  assertTrue(value.nil(null,"SME","bank",channels,Set.of()).isEmpty());
  assertTrue(value.nil(null,"XML","excluded",channels,Set.of("excluded")).isEmpty());
  assertTrue(value.nil(null,null,"bank",channels,Set.of()).isEmpty()); assertEquals(0,value.execute());
 }
}'''.replace('PACKAGE', package)
    junit = next(item for item in request['known_dependencies'] if item['artifact_id'] == 'junit-jupiter')
    evidence = request['sources'][0]['identity']
    return dict(contracts={key: dict(component_id=key, apis=[dict(type_name=package+'.Primitives',
        method_signatures=['public int execute()'])], source_entry_points=request['source_entry_points'][key],
        evidence_ids=[evidence], dependencies=request['components'][key]['dependencies'], configuration_mode='parameterized',
        configuration_parameters={'pattern':'String'}, runtime_inputs={'channel':'String','application':'String','settings':'Set<String>'})},
        files=[dict(path=main_path,content=main),dict(path=test_path,content=test)], dependencies=[junit],
        coverage={key:[test_path] for key in request['requirements']}, evidence_ids=[evidence],
        checklist_implementations={item['id']:[dict(path=main_path,excerpt=main)] for item in request['parser_checklist']})


def test_request_uses_exact_source_and_parser_items_only(component_case):
    _, _, profile, _, plan, group, boundaries = component_case
    request, instruction = build_component_request(plan, group, boundaries, [], profile)
    assert basic_group(plan, group)
    assert len(request['sources']) == 1 and request['sources'][0]['content'] == PRIMITIVES
    assert request['parser_checklist'] and all(item['source_identity'] == 'source:example.Primitives' for item in request['parser_checklist'])
    assert 'example.Unrelated' not in json.dumps(request) and 'class Work' not in json.dumps(request)
    assert 'both directions' in instruction and 'runtime-dependent' in instruction


def test_oversized_indivisible_group_is_not_summarized_or_sent(component_case):
    conn, config, profile, preparation, plan, group, boundaries = component_case
    source = Path(plan.components[group.members[0]].provenance['source_file'])
    text = source.read_text() + '\n/*' + 'oversized ' * 10000 + '*/'
    source.write_text(text, encoding='utf-8', newline='\n')
    from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
    revised = plan.model_copy(deep=True); revised.components[group.members[0]].provenance['source_hash'] = file_digest(source)
    updated = deepcopy(preparation)
    for item in updated['operations'].values():
        for unit in item['units']:
            for evidence in unit['sources']:
                if evidence['identity'] == revised.components[group.members[0]].provenance['definition_id']:
                    evidence.update(content=text, content_hash=file_digest(source))
    boundaries = build_boundary_report(updated)
    low = profile.model_copy(update={'behavior_context_chars':60000})
    with pytest.raises(ValueError, match='context budget'):
        build_component_request(revised, group, boundaries, [], low)
    assert conn.execute('SELECT count(*) FROM behavior_attempts').fetchone()[0] == 0


def test_component_generation_is_gated_without_execution(component_case):
    conn, config, profile, _, plan, group, boundaries = component_case
    request, instruction = build_component_request(plan, group, boundaries, [], profile)
    with pytest.raises(ValueError, match='gated'):
        generate(conn, config, profile, 'component_generation', group.group_id, instruction, request, NativeComponentBundle,
                 model_call=lambda *a: pytest.fail('No model outside the scope'))


def test_real_maven_generation_correction_and_unchanged_reuse(component_case, tmp_path):
    conn, config, profile, preparation, plan, group, _ = component_case
    calls = []
    def model(instruction, encoded):
        request = json.loads(encoded); calls.append(request)
        if len(calls) == 2:
            assert 'missingVariable' in request['correction_feedback']
        return json.dumps(native_fixture(request, bad=len(calls)==1))
    directory = tmp_path / 'reports'
    from tests.runtime.test_scoped_native import actual_build
    convert_basic_components(conn, config, profile, directory, preparation, None, model_call=model, context_factory=actual_build)
    report = json.loads((directory/'reports/3_dependency_closure_and_component_conversion/component-generation.json').read_text())
    assert report['component_validated'] == 1, report
    assert len(calls) == 2 and report['accepted_units'] == report['accepted_operations'] == 0
    assert not report['behavioral_acceptance']
    convert_basic_components(conn, config, profile, directory, preparation, None,
        model_call=lambda *a: pytest.fail('Unchanged components must reuse without model calls'), context_factory=actual_build)
    report = json.loads((directory/'reports/3_dependency_closure_and_component_conversion/component-generation.json').read_text())
    assert report['reused_components'] == 1, report
    row = conn.execute("SELECT data_json FROM behavior_snapshots WHERE category='unit_verification'").fetchone()
    assert row is None


@pytest.mark.parametrize('problem', ['missing_contract', 'changed_entry', 'wrong_package', 'missing_checklist', 'missing_coverage', 'unfinished', 'test_citation'])
def test_invalid_component_candidates_never_reach_a_build(component_case, problem):
    conn, config, profile, preparation, plan, group, boundaries = component_case
    request, _ = build_component_request(plan, group, boundaries, [], profile)
    data = native_fixture(request)
    key = group.members[0]
    if problem == 'missing_contract': data['contracts'] = {}
    if problem == 'changed_entry': data['contracts'][key]['source_entry_points'] = ['invented']
    if problem == 'wrong_package': data['contracts'][key]['apis'][0]['type_name'] = 'com.company.generated.other.Primitives'
    if problem == 'missing_checklist': data['checklist_implementations'] = {}
    if problem == 'missing_coverage': data['coverage'] = {}
    if problem == 'unfinished': data['unresolved_questions'] = ['Missing dependency implementation']
    if problem == 'test_citation':
        first = next(iter(data['checklist_implementations']))
        data['checklist_implementations'][first] = [dict(path=data['files'][1]['path'], excerpt='public class PrimitivesTest')]
    from runtime.component_conversion.validation import ComponentCandidateValidator
    candidate = ComponentCandidateValidator(conn, config, profile, plan, group, request, Path(config.output_root)/'components',
        lambda *a: pytest.fail('Invalid candidate reached Maven'), {}, [])
    with component_execution(conn, config, profile, None, preparation), pytest.raises(ValueError):
        candidate(NativeComponentBundle.model_validate(data))
    assert not candidate.results


def test_contract_request_delivers_exact_source_ids_and_parameterized_mode(component_case):
    _,_,profile,_,plan,group,boundaries=component_case
    request,instruction=build_component_request(plan,group,boundaries,[],profile)
    key=group.members[0]
    expected=request['expected_contract_fields'][key]
    assert expected['component_id']==key and expected['configuration_mode']=='parameterized'
    assert expected['source_entry_points']==request['source_entry_points'][key]
    assert expected['evidence_ids']==[request['sources'][0]['identity']]
    assert set(expected['evidence_ids']).issubset(request['allowed_evidence_ids'])
    assert key not in request['allowed_evidence_ids'] and 'expected_contract_fields' in instruction
    coverage = request['coverage_response_example']['coverage']
    assert set(coverage) == set(request['requirements'])
    assert 'business' not in coverage
    assert all(paths == ['src/test/java/' + request['native_package'].replace('.', '/') +
                         '/ComponentBehaviorTest.java'] for paths in coverage.values())
    assert '"coverage": {"business"' not in instruction


def test_wrong_evidence_error_names_the_usable_source_ids_without_accepting_them(component_case):
    conn,config,profile,preparation,plan,group,boundaries=component_case
    request,_=build_component_request(plan,group,boundaries,[],profile)
    data=native_fixture(request);key=group.members[0]
    data['contracts'][key]['evidence_ids']=[key]
    from runtime.component_conversion.validation import ComponentCandidateValidator
    candidate=ComponentCandidateValidator(conn,config,profile,plan,group,request,Path(config.output_root)/'components',
        lambda *args:pytest.fail('Wrong evidence reached Maven'),{},[])
    with component_execution(conn,config,profile,None,preparation),pytest.raises(ValueError) as rejected:
        candidate(NativeComponentBundle.model_validate(data))
    assert 'allowed_evidence_ids' in str(rejected.value) and request['sources'][0]['identity'] in str(rejected.value)
    assert not candidate.results


def test_component_scope_rejects_changed_request_source_and_legacy_mode(component_case):
    conn, config, profile, preparation, plan, group, boundaries = component_case
    request, instruction = build_component_request(plan, group, boundaries, [], profile)
    changed = deepcopy(request); changed['sources'][0]['content'] += '// invented source'
    with component_execution(conn, config, profile, None, preparation), pytest.raises(ValueError, match='source evidence'):
        generate(conn, config, profile, 'component_generation', group.group_id, instruction, changed, NativeComponentBundle,
            model_call=lambda *a: pytest.fail('Changed source reached model'))
    with pytest.raises(ValueError, match='explicit component_first'):
        with component_execution(conn, config, profile.model_copy(update={'scoped_native_mode':'behavior_units_v1'}), None, preparation):
            pytest.fail('Legacy mode entered component generation')


def test_real_scoped_component_mode_keeps_plan_approval_before_generation(tmp_path, scoped_mapper, monkeypatch):
    from tests.runtime.test_scoped_native import scoped_state
    from runtime.scoped_native.runner import resume_scoped_pipeline
    from runtime.java_toolchain import java_scope
    from tools.state_store_tools.runs import get_run
    conn, config = scoped_state(tmp_path, scoped_mapper)
    profile = PipelineConfiguration(source_root=config.source_root, scoped_java_project='.', conversion_strategy='behavior_units',
        scoped_native_mode='component_first_v1', plan_approval_policy='human', java_version=25)
    monkeypatch.setattr('runtime.component_conversion.runner.convert_basic_components', lambda *a, **k: pytest.fail('Pending approval reached CF3'))
    try:
        with java_scope(profile):
            resume_scoped_pipeline(conn, config, profile, tmp_path/'reports', model_call=lambda *a: pytest.fail('Pending approval called AI'))
        assert get_run(conn, config.run_id)['current_phase'] == 'conversion_plan_pending'
    finally:
        conn.close()


def test_real_scoped_component_context_rechecks_source_checkpoints(tmp_path, scoped_mapper):
    from tests.runtime.test_scoped_native import scoped_state
    from runtime.java_toolchain import java_scope
    from runtime.component_conversion.scope import require_component_task
    from tools.conversion_tools.scoped_workflow.preparation import prepare_scoped_workflow
    from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale
    from tools.source_discovery_tools.classpath import discover_java_classpath
    conn, config = scoped_state(tmp_path, scoped_mapper)
    profile = PipelineConfiguration(source_root=config.source_root, scoped_java_project='.', conversion_strategy='behavior_units',
        scoped_native_mode='component_first_v1', java_version=25)
    try:
        with java_scope(profile):
            classpath = discover_java_classpath(config.source_root, [], {})
            preparation = prepare_scoped_workflow(conn, config, profile, classpath_index=classpath)
            plan = build_component_plan(preparation['operations'])
            group = next(group for group in plan.groups if basic_group(plan, group) and group.wave is not None)
            source = Path(plan.components[group.members[0]].provenance['source_file'])
            with component_execution(conn, config, profile, classpath, preparation):
                require_component_task(conn, config, profile, group.group_id)
                source.write_bytes(source.read_bytes() + b'\n// stale original source')
                with pytest.raises((ScopedCheckpointStale, ValueError)):
                    require_component_task(conn, config, profile, group.group_id)
    finally:
        conn.close()


def test_bank_primitive_requests_retain_actual_implementations(tmp_path, scoped_mapper, boundary_tool):
    from test_bank_boundary_harness import _prepare_bank
    preparation = _prepare_bank(tmp_path, scoped_mapper)
    plan = build_component_plan(preparation['operations'])
    profile = PipelineConfiguration(java_version=25, conversion_strategy='behavior_units', scoped_native_mode='component_first_v1')
    expected = {'CCString', 'CCDate', 'CCMandatory', 'CCNullToZero', 'NilDecorator'}
    units = {unit['unit_id']: unit for operation in preparation['operations'].values() for unit in operation['units']}
    selected = {min(node.unit_ids, key=lambda key:sum(len(source['content']) for source in units[key]['sources']))
                for node in plan.components.values() if node.kind=='java_implementation' and node.label.rsplit('.',1)[-1] in expected}
    original = deepcopy(preparation)
    for operation in original['operations'].values():
        operation['units'] = [unit for unit in operation['units'] if unit['unit_id'] in selected]
    boundaries = build_boundary_report(original, tool_jar=boundary_tool)
    found = set()
    for group in plan.groups:
        labels = {plan.components[key].label.rsplit('.',1)[-1] for key in group.members if plan.components[key].kind=='java_implementation'}
        if not labels.intersection(expected): continue
        assert basic_group(plan, group)
        request, _ = build_component_request(plan, group, boundaries, [], profile)
        for source in request['sources']:
            original = plan.components[source['component_id']].provenance
            assert source['content'] == Path(original['source_file']).read_text(encoding='utf-8-sig')
            assert source['content_hash'] == original['source_hash']
        assert 'GetAccountDetailsSP' not in json.dumps(request)
        found.update(labels.intersection(expected))
    assert found == expected

