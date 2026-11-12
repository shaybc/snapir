"""Exercise inherited OP-step analysis through request, authorization, and reuse handoffs."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.component_conversion.requests import build_component_request
from runtime.component_conversion.source_evidence import validate_component_sources
from runtime.component_conversion.steps import source_bindings
from tools.behavior_verification.boundaries import build_boundary_report
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.component_identity import component_group
from test_behavior_verification_boundaries import boundary_tool
from test_component_graph import origin, step, operation


@pytest.fixture(scope='module', autouse=True)
def selected_jdk():
    with java_scope(PipelineConfiguration(java_version=25)): yield


def step_case(folder, definitions, *, implementation='example.Child', framework=(), tool=None):
    """Keep real source hashes/supporting-source ownership while varying the hierarchy."""
    folder.mkdir(parents=True, exist_ok=True)
    originals = []
    for name, (text, dependencies) in definitions.items():
        metadata, content = origin(name, dependencies, text)
        path = folder / (name.replace('.', '/') + '.java')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')
        metadata['source_file'] = str(path)
        originals.append((metadata, content))
    value = step('selected-step', implementation=implementation)
    preparation = dict(operations={'BANK/Flow': operation([value], originals)})
    plan = build_component_plan(preparation['operations'])
    assert not plan.issues, plan.issues
    preparation['component_plan'] = plan.model_dump(mode='json')
    boundaries = build_boundary_report(preparation, tool_jar=tool)
    assert boundaries['counts']['identified'] == 1, boundaries
    profile = PipelineConfiguration(source_root=str(folder), java_version=25,
        conversion_strategy='behavior_units', scoped_native_mode='component_first_v1', framework_jars=list(map(str, framework)))
    key = next(key for key, node in plan.components.items() if node.kind == 'java_implementation' and node.label == implementation)
    return SimpleNamespace(plan=plan, profile=profile, preparation=preparation, boundaries=boundaries,
        units={value['unit_id']: value}, implementation=component_group(plan, key),
        occurrence=component_group(plan, plan.unit_roots[value['unit_id']]))


def request_for(case, occurrence=False):
    return build_component_request(case.plan, case.occurrence if occurrence else case.implementation,
        case.boundaries, [], case.profile, check_budget=False, units=case.units)[0]


def inherited_definitions(depth=1, override=False):
    definitions = {
        'example.Wrapper': ('package example; public abstract class Wrapper { public int execute() throws Exception { return ccExecute(); } protected abstract int ccExecute() throws Exception; }', []),
        'example.Stored': ('package example; public class Stored extends Wrapper { protected int ccExecute() throws Exception { return 17; } public int unused(){return 999;} }', ['example.Wrapper']),
        'example.Noise': ('package example; public class Noise { public int unrelated(){return 888;} }', []),
    }
    parent = 'example.Stored'
    for index in range(depth):
        name = 'example.Layer' + str(index)
        definitions[name] = ('package example; public class Layer' + str(index) + ' extends ' + parent.rsplit('.', 1)[-1] + ' {}', [parent])
        parent = name
    body = 'protected int ccExecute(){return 37;}' if override else ''
    definitions['example.Child'] = ('package example; public class Child extends ' + parent.rsplit('.', 1)[-1] + ' {' + body + '}', [parent, 'example.Noise'])
    return definitions


@pytest.mark.parametrize('depth', [0, 3])
@pytest.mark.parametrize('occurrence', [False, True])
def test_inherited_execution_and_business_methods_reach_step_request(tmp_path, boundary_tool, depth, occurrence):
    case = step_case(tmp_path / 'sources', inherited_definitions(depth), tool=boundary_tool)
    before = deepcopy(case.boundaries)
    request = request_for(case, occurrence)
    entries = next(iter(request['source_entry_points'].values()))
    assert 'example.Wrapper.execute()' in entries
    assert 'example.Stored.ccExecute()' in entries
    assert not any('unused' in entry or 'unrelated' in entry for entry in entries)
    facts = request['parser_checklist']
    assert any(item['source_identity'] == 'source:example.Stored' and '17' in item['excerpt'] for item in facts)
    assert not any('999' in item['excerpt'] or '888' in item['excerpt'] for item in facts)
    assert case.boundaries == before
    boundary = case.boundaries['boundaries']['selected-step']
    assert boundary['legacy_method']['declaring_class'] == 'example.Wrapper'
    group = case.occurrence if occurrence else case.implementation
    validate_component_sources(case.plan, group, source_bindings(case.plan, group), request['sources'], units=case.units)
    assert request['kind'] == ('configured_step' if occurrence else 'step_implementation')


def test_direct_entry_still_excludes_unreachable_concrete_methods(tmp_path, boundary_tool):
    definitions = {'example.Child': ('package example; public class Child { public int execute() throws Exception { return 7; } public int unused(){return 999;} }', [])}
    case = step_case(tmp_path / 'sources', definitions, tool=boundary_tool)
    request = request_for(case)
    assert next(iter(request['source_entry_points'].values())) == ['example.Child.execute()']
    assert not any('999' in item['excerpt'] for item in request['parser_checklist'])


def test_override_retains_existing_dispatch_uncertainty(tmp_path, boundary_tool):
    case = step_case(tmp_path / 'sources', inherited_definitions(2, override=True), tool=boundary_tool)
    request = request_for(case)
    entries = next(iter(request['source_entry_points'].values()))
    assert {'example.Wrapper.execute()', 'example.Stored.ccExecute()', 'example.Child.ccExecute()'} <= set(entries)
    graph = case.boundaries['boundaries']['selected-step']['reachable_slice']
    assert any(edge['uncertain'] for edge in graph['edges'])
    assert any(fact['path_certainty'] == 'uncertain' for fact in request['parser_checklist'] if fact['source_identity'] in {'source:example.Stored', 'source:example.Child'})


def test_inherited_supporting_sources_remain_hash_checked(tmp_path, boundary_tool):
    case = step_case(tmp_path / 'sources', inherited_definitions(), tool=boundary_tool)
    path = tmp_path / 'sources/example/Stored.java'
    path.write_text(path.read_text() + ' // changed', encoding='utf-8')
    with pytest.raises(ValueError, match='changed|revision|hash'):
        request_for(case)


def test_step_entry_failure_keeps_actual_analysis_reason(tmp_path, boundary_tool):
    case = step_case(tmp_path / 'sources', inherited_definitions(), tool=boundary_tool)
    boundary = case.boundaries['boundaries']['selected-step']
    boundary.update(analysis_status='verification_incomplete', issues=['Superclass type cannot be resolved: vendor.MissingParent'])
    boundary['reachable_slice'] = None
    with pytest.raises(ValueError, match='vendor.MissingParent'):
        request_for(case)


@pytest.mark.parametrize('field', ['node_hash', 'fact_hash', 'missing_entry_source'])
def test_inherited_graph_provenance_is_not_relaxed(tmp_path, boundary_tool, field):
    case = step_case(tmp_path / 'sources', inherited_definitions(), tool=boundary_tool)
    boundary = case.boundaries['boundaries']['selected-step']
    if field == 'node_hash':
        node = next(node for node in boundary['reachable_slice']['nodes'] if node['signature'] == 'example.Stored.ccExecute()')
        node['source_hash'] = 'changed'
    elif field == 'fact_hash':
        fact = next(item for item in boundary['parser_checklist']['items'] if item['source_identity'] == 'source:example.Stored')
        fact['source_hash'] = 'changed'
    else:
        for node in case.plan.components.values():
            node.provenance['supporting_sources'] = [source for source in node.provenance.get('supporting_sources', []) if source['fqcn'] != 'example.Wrapper']
    with pytest.raises(ValueError, match='revision|provenance'):
        request_for(case)


@pytest.mark.parametrize('outdated', [False, True])
def test_reuse_checks_inherited_obligations_without_clearing_run_state(tmp_path, boundary_tool, monkeypatch, outdated):
    import sqlite3
    from runtime.component_conversion import runner
    from tools.state_store_tools.behavior_units import initialize
    case = step_case(tmp_path / 'sources', inherited_definitions(), tool=boundary_tool)
    request = request_for(case)
    saved = deepcopy(request)
    if outdated:
        saved['source_entry_points'] = {key: ['example.Wrapper.execute()'] for key in saved['source_entry_points']}
        saved['parser_checklist'] = [fact for fact in saved['parser_checklist'] if fact['source_identity'] == 'source:example.Child']
    artifact = tmp_path / 'saved-component'
    artifact.mkdir()
    receipt = artifact / 'validation.json'
    receipt.write_text(json.dumps(saved), encoding='utf-8')
    before = receipt.read_bytes()
    key = case.implementation.members[0]
    result = SimpleNamespace(artifact_root=str(artifact), validation_report='validation.json')
    verified = []
    monkeypatch.setattr(runner, 'require_component_task', lambda *a, **k: None)
    monkeypatch.setattr(runner, 'revalidate_components', lambda *a, **k: lambda *args: verified.append(True))
    def reuse(*args, validator, **kwargs):
        validator({}, {key: result})
        return {key: result}
    monkeypatch.setattr(runner, 'reuse_component_result', reuse)
    class NeedsRegeneration(Exception): pass
    def regenerate(*args, **kwargs): raise NeedsRegeneration()
    monkeypatch.setattr(runner, 'native_format_prerequisites', regenerate)
    with sqlite3.connect(':memory:') as conn:
        initialize(conn)
        config = SimpleNamespace(run_id='same-saved-run')
        call = lambda: runner._convert_group(conn, config, case.profile, case.plan, case.implementation,
            case.boundaries, tmp_path / 'output', None, None, units=case.units)
        if outdated:
            with pytest.raises(NeedsRegeneration): call()
            assert not verified
        else:
            assert call()['reused'] is True
            assert verified == [True]
        assert conn.execute('SELECT count(*) FROM behavior_attempts').fetchone()[0] == 0
    assert receipt.read_bytes() == before


def test_test_based_mode_keeps_inherited_obligations_without_parser_facts(tmp_path, boundary_tool):
    case = step_case(tmp_path / 'sources', inherited_definitions(2), tool=boundary_tool)
    case.profile.executable_verification.mode = 'test_based_v1'
    request = request_for(case, occurrence=True)
    assert not request['parser_checklist']
    assert {'example.Wrapper.execute()', 'example.Stored.ccExecute()'} <= set(next(iter(request['source_entry_points'].values())))
    assert any(source['identity'] == 'source:example.Stored' for source in request['sources'])


def test_unreachable_graph_node_does_not_become_an_entry_obligation(tmp_path, boundary_tool):
    from runtime.component_conversion.step_entry_evidence import step_entry_evidence
    case = step_case(tmp_path / 'sources', inherited_definitions(), tool=boundary_tool)
    request = request_for(case)
    boundary = deepcopy(case.boundaries['boundaries']['selected-step'])
    node = deepcopy(next(node for node in boundary['reachable_slice']['nodes'] if node['signature'] == 'example.Stored.ccExecute()'))
    node.update(id='unreachable-node', signature='example.Stored.notAnEntry()')
    boundary['reachable_slice']['nodes'].append(node)
    component = case.plan.components[case.implementation.members[0]]
    methods, _ = step_entry_evidence(boundary, request['sources'], component.component_id, component.provenance)
    assert 'example.Stored.notAnEntry()' not in methods


@pytest.mark.parametrize('occurrence', [False, True])
def test_authorized_step_request_retains_inherited_source_checks(tmp_path, boundary_tool, monkeypatch, occurrence):
    from runtime.component_conversion.scope import component_execution, require_component_task
    from tools.state_store_tools.db import get_connection, create_all_tables
    from tools.state_store_tools.runs import upsert_run
    case = step_case(tmp_path / 'sources', inherited_definitions(), tool=boundary_tool)
    request = request_for(case, occurrence)
    group = case.occurrence if occurrence else case.implementation
    config = SimpleNamespace(run_id='inherited-step', source_root=case.profile.source_root, output_root=str(tmp_path / 'output'))
    conn = get_connection(str(tmp_path / 'state.db'))
    try:
        create_all_tables(conn)
        upsert_run(conn, run_id=config.run_id, run_mode='conversion')
        # This fixture has no imported Composer vault; source authorization stays real.
        monkeypatch.setattr('runtime.component_conversion.scope.validate_checkpoints', lambda *a, **k: None)
        with component_execution(conn, config, case.profile, None, case.preparation, include_steps=True, boundaries=case.boundaries):
            require_component_task(conn, config, case.profile, group.group_id, request)
            changed = deepcopy(request)
            inherited = next(source for source in changed['sources'] if source['identity'] == 'source:example.Stored')
            inherited['content'] += '// forged source'
            with pytest.raises(ValueError, match='source evidence'):
                require_component_task(conn, config, case.profile, group.group_id, changed)
    finally:
        conn.close()


def test_local_overload_does_not_hide_inherited_execution_entry(tmp_path, boundary_tool):
    definitions = inherited_definitions(2)
    text, dependencies = definitions['example.Child']
    definitions['example.Child'] = (text.replace('{}', '{public int execute(int ignored){return 999;}}'), dependencies)
    case = step_case(tmp_path / 'sources', definitions, tool=boundary_tool)
    methods = next(iter(request_for(case)['source_entry_points'].values()))
    assert 'example.Wrapper.execute()' in methods
    assert 'example.Child.execute(int)' not in methods


def test_inherited_hook_reaches_business_override_without_local_execution_methods(tmp_path, boundary_tool):
    definitions = inherited_definitions(2)
    definitions['example.Stored'] = ('package example; public class Stored extends Wrapper { protected int ccExecute() throws Exception { return business(); } protected int business(){return 17;} }', ['example.Wrapper'])
    child, dependencies = definitions['example.Child']
    definitions['example.Child'] = (child.replace('{}', '{protected int business(){return 37;}}'), dependencies)
    case = step_case(tmp_path / 'sources', definitions, tool=boundary_tool)
    request = request_for(case, occurrence=True)
    methods = next(iter(request['source_entry_points'].values()))
    assert {'example.Wrapper.execute()', 'example.Stored.ccExecute()', 'example.Child.business()'} <= set(methods)
    assert not any(method.startswith('example.Child.execute(') or method.startswith('example.Child.ccExecute(') for method in methods)
    assert any(fact['source_identity'] == 'source:example.Child' and '37' in fact['excerpt'] for fact in request['parser_checklist'])
