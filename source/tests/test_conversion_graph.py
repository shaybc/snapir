"""Converter-only provenance, bounded navigation and diagnostics without conversion side effects."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from models.conversion_graph import ConversionGraph
from tools.conversion_tools.conversion_graph_records import graph_from_records
from tools.run_diagnostics.conversion_records import load_graph
from tools.run_diagnostics.superscope_model import build_model
from tools.run_diagnostics.superscope_export import export_model
from tools.run_diagnostics.html_report import write_dashboard, powershell_command
from test_behavior_verification_boundaries import boundary_tool, unit, source, prepared


def records():
    plan = dict(fingerprint='plan-revision', unit_roots={'write': 'string', 'read': 'string'},
        components={
            'string': dict(label='example.CCString', kind='java_implementation', status='source_recorded',
                unit_ids=['write', 'read'], dependencies=['dependency'], dependency_reasons={'dependency': ['recorded required_classes']},
                provenance=dict(definition_id='string-source', source_hash='string-hash'), issues=[]),
            'dependency': dict(label='example.Dependency', kind='unresolved_dependency', status='unresolved',
                unit_ids=['write', 'read'], dependencies=[], provenance={}, issues=['Class source not found'])},
        groups=[dict(group_id='main', members=['string'], dependencies=['prerequisite']),
                dict(group_id='prerequisite', members=['dependency'], dependencies=[])])
    boundaries = dict(boundaries={}, diagnostic_structure={})
    for identity, kind, method, parameters, returns in [('write', 'response_format', 'format', ['Context'], 'java.lang.String'),
            ('read', 'request_unformat', 'unformat', ['java.lang.String', 'Context'], 'void')]:
        boundaries['boundaries'][identity] = dict(kind=kind, implementation_class='example.CCString', source_manifest_hash='sources',
            analysis_status='identified', issues=[], method_name=method, parameter_contract=parameters, return_contract=returns,
            legacy_method=dict(declaring_class='example.Parent', signature='example.Parent.' + method + '(' + ', '.join(parameters) + ')',
                return_type=returns, source_identity='parent-source', source_hash='parent-hash'))
        boundaries['diagnostic_structure'][identity] = dict(classes=[
            dict(name='example.CCString', source_identity='string-source', source_hash='string-hash', status='recorded',
                 parents=[dict(name='example.Parent', relation='extends')], fields=[]),
            dict(name='example.Parent', source_identity='parent-source', source_hash='parent-hash', status='recorded',
                 parents=[dict(name='framework.Base', relation='extends')], fields=[dict(name='value', type='example.Dependency')]),
            dict(name='framework.Base', status='recorded', parents=[], fields=[])], issues=[])
    reason = 'Required native prerequisite is not component_validated: prerequisite'
    outcomes = dict(groups={'main': dict(status='incomplete', members=['string'], reason=reason),
        'prerequisite': dict(status='incomplete', members=['dependency'], reason='Class source not found')})
    blockers = [dict(plan_fingerprint='plan-revision', group_id='main', dependency_group='prerequisite', reason=reason)]
    return plan, boundaries, outcomes, blockers


def graph_fixture():
    plan, boundaries, outcomes, blockers = records()
    return graph_from_records('saved-run', plan, boundaries, {}, outcomes, blockers=blockers)


def save_graph(root, graph):
    path = root / 'state/conversion-graph.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.model_dump_json(indent=2), encoding='utf-8')
    return path


def test_converter_relations_entry_owners_and_blockers_are_exact():
    plan, boundaries, outcomes, blockers = records()
    before = deepcopy((plan, boundaries, outcomes, blockers))
    graph = graph_from_records('saved-run', plan, boundaries, {}, outcomes, blockers=blockers)
    parent = next(node for node in graph.nodes.values() if node['label'] == 'example.Parent')
    assert {entry['direction'] for entry in parent['entry_points'] if entry['role'] == 'declares'} == {'format', 'unformat'}
    assert all(entry['declaring_class'] == 'example.Parent' for entry in parent['entry_points'])
    assert any(edge['relation'] == 'extends' and edge['from'] == 'string' and edge['to'] == parent['id'] for edge in graph.edges)
    assert any(edge['relation'] == 'has_field' and edge['from'] == parent['id'] for edge in graph.edges)
    assert any(edge['relation'] == 'blocked_by' and edge['to'] == 'dependency' for edge in graph.edges)
    assert graph.nodes['dependency']['issues'] == ['Class source not found']
    assert not any(edge['relation'] == 'converted_to' for edge in graph.edges)
    assert before == (plan, boundaries, outcomes, blockers)


@pytest.mark.parametrize('state,reused', [('component_validated', False), ('component_validated', True), ('incomplete', False)])
def test_build_success_and_reuse_are_not_comparison_acceptance(state, reused):
    plan, boundaries, outcomes, _ = records()
    outcomes['groups']['main'] = dict(status=state, members=['string'], reused=reused, validation_scope='build_and_tests')
    detail = dict(plan_fingerprint=plan['fingerprint'], result_revision='result', native_apis=['generated.StringFormat'],
        comparisons={'write': dict(status='matched'), 'read': dict(status='comparison_unavailable')}, evidence=dict(record='validation', sha256='proof'))
    graph = graph_from_records('run', plan, boundaries, {}, outcomes, validation={'string': detail})
    assert graph.nodes['string']['status'] == state
    converted = [edge for edge in graph.edges if edge['relation'] == 'converted_to']
    assert bool(converted) is (state == 'component_validated')
    if converted:
        assert graph.nodes['string']['comparisons']['read']['status'] == 'comparison_unavailable'


def test_missing_direction_never_borrows_another_entry():
    plan, boundaries, outcomes, _ = records()
    read = boundaries['boundaries']['read']
    read.pop('legacy_method')
    read.update(analysis_status='verification_incomplete', issues=['Entry method must resolve uniquely (matches=0)'])
    graph = graph_from_records('run', plan, boundaries, {}, outcomes)
    entry = next(item for item in graph.nodes['string']['entry_points'] if item['direction'] == 'unformat')
    assert 'signature' not in entry and 'unformat' in entry['expected_signature']
    assert 'declaring_class' not in entry
    assert not any(item.get('direction') == 'unformat' and item.get('role') == 'declares'
        for node in graph.nodes.values() for item in node['entry_points'])


def test_stale_blocker_or_validation_is_not_current_evidence():
    plan, boundaries, outcomes, blockers = records()
    blockers[0]['plan_fingerprint'] = 'old-plan'
    graph = graph_from_records('run', plan, boundaries, {}, outcomes, blockers=blockers)
    assert not any(edge['relation'] == 'blocked_by' for edge in graph.edges)


def test_preparation_error_retains_requested_classes_without_inventing_entries(tmp_path):
    from runtime.component_conversion.conversion_trace import record_preparation_failure
    config = SimpleNamespace(run_id='failed-preparation')
    profile = SimpleNamespace(selected_components=['example.Missing'])
    record_preparation_failure(config, profile, tmp_path, ValueError('Selected component source is unavailable'))
    graph = load_graph(tmp_path)
    root = graph.nodes[graph.roots[0]]
    assert root['label'] == 'example.Missing' and root['status'] == 'not_run'
    assert not root['entry_points']
    assert any(node.get('reason') == 'Selected component source is unavailable' for node in graph.nodes.values())
    assert any(edge['relation'] == 'blocked_by' for edge in graph.edges)


def test_operation_snapshot_does_not_borrow_the_latest_other_operation_plan(tmp_path):
    import sqlite3
    database = tmp_path / 'state/migration.db'
    database.parent.mkdir()
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE conversion_component_plans (run_id TEXT, plan_json TEXT)')
        conn.execute('INSERT INTO conversion_component_plans VALUES (?,?)', (tmp_path.name, json.dumps(records()[0])))
    operation = tmp_path / 'operation_workflows/older-operation'
    operation.mkdir(parents=True)
    graph = load_graph(operation)
    assert not graph.nodes


def test_validation_trace_keeps_native_ownership_after_publication(tmp_path):
    from runtime.component_conversion.conversion_trace import record_validation, record_trace
    plan, boundaries, outcomes, _ = records()
    artifact = tmp_path / 'generated/components/result'; artifact.mkdir(parents=True)
    report = dict(standalone_comparisons={'write': dict(status='matched'), 'read': dict(status='comparison_unavailable')})
    text = json.dumps(report)
    (artifact / 'validation.json').write_text(text)
    result = SimpleNamespace(artifact_root=str(artifact), validation_report='validation.json',
        validation_report_hash=hashlib.sha256(text.encode()).hexdigest())
    config = SimpleNamespace(run_id='run', output_root=str(tmp_path / 'generated'))
    record_validation(config, SimpleNamespace(fingerprint=plan['fingerprint']),
        {'string': dict(apis=[dict(type_name='nativecode.StringFormat')])}, {'string': result})
    outcomes['groups']['main'].update(status='component_validated')
    record_trace(config, tmp_path, plan, boundaries, {}, outcomes)
    graph = load_graph(tmp_path)
    assert any(node['label'] == 'nativecode.StringFormat' for node in graph.nodes.values())
    assert graph.nodes['string']['comparisons']['read']['status'] == 'comparison_unavailable'


def test_four_levels_keep_deep_shared_dependencies_and_cycles():
    nodes = {str(number): dict(id=str(number), label='Class' + str(number), kind='class', status='not_recorded') for number in range(9)}
    edges = [dict(id='edge' + str(number), **{'from': str(number), 'to': str(number + 1)}, relation='uses', evidence={}) for number in range(8)]
    edges += [dict(id='cycle', **{'from': '8', 'to': '0'}, relation='uses', evidence={}),
              dict(id='shared', **{'from': '1', 'to': '7'}, relation='contains', evidence={})]
    graph = ConversionGraph(run_id='deep', roots=['0'], nodes=nodes, edges=edges)
    before = graph.model_dump_json()
    model, views, mapping, _ = build_model(graph, '0')
    assert max(item['level'] for item in mapping.values()) == 4
    assert {item['canonical_id'] for item in mapping.values()} == set(nodes)
    assert all(edge['id'] in {json.loads(item['details'])['id'] for item in model['connections']} for edge in edges)
    assert any('8' == item['canonical_id'] and item['level'] == 4 for item in mapping.values())
    assert all('layout' not in view for view in views)
    assert before == graph.model_dump_json()


def test_export_uses_records_without_source_and_preserves_existing_models(tmp_path, monkeypatch):
    save_graph(tmp_path, graph_fixture())
    def forbidden(*args, **kwargs):
        pytest.fail('Exporter invoked conversion or source analysis')
    monkeypatch.setattr('tools.behavior_verification.boundaries.build_boundary_report', forbidden)
    monkeypatch.setattr('tools.source_discovery_tools.discover_java_sources', forbidden)
    output = export_model(tmp_path, 'string', tmp_path / 'export')
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['max_levels'] == 4
    model = yaml.safe_load((output / '.superscope/model.yaml').read_text(encoding='utf-8'))
    assert any('entry-format' in tag['name'] for tag in model['tagGroups'][0]['tags'])
    assert (output / 'converter-records.json').is_file()
    before = (output / '.superscope/model.yaml').read_bytes()
    with pytest.raises(ValueError, match='already exists'):
        export_model(tmp_path, 'string', output)
    assert (output / '.superscope/model.yaml').read_bytes() == before


def test_dashboard_only_copies_commands_and_escapes_saved_text(tmp_path):
    graph = graph_fixture()
    graph.nodes['string']['label'] = '<script>alert("bad")</script>'
    graph.nodes['string']['reason'] = '<img src=x onerror=alert(1)>'
    save_graph(tmp_path, graph)
    page = write_dashboard(tmp_path)
    text = page.read_text(encoding='utf-8')
    assert '&lt;script&gt;alert' in text and '<img src=x' not in text
    assert 'Copy generation command' in text and '--focus' in text
    assert not (tmp_path / 'reports/superscope').exists()
    command = powershell_command(tmp_path / "a'b$(`test)", "component'quoted")
    assert "a''b$(`test)" in command and "'component''quoted'" in command


def test_older_run_marks_missing_relationships_without_analyzing(tmp_path):
    plan, boundaries, outcomes, _ = records()
    boundaries.pop('diagnostic_structure')
    path = tmp_path / 'state/standalone-preparation.json'
    path.parent.mkdir()
    path.write_text(json.dumps(dict(component_plan=plan, boundaries=boundaries)))
    stage = tmp_path / 'reports/3_dependency_closure_and_component_conversion'
    stage.mkdir(parents=True)
    (stage / 'component-generation.json').write_text(json.dumps(outcomes))
    graph = load_graph(tmp_path)
    assert any('Older run' in issue for issue in graph.issues)
    assert not any(edge['relation'] == 'extends' for edge in graph.edges)
    assert any(edge['relation'] == 'entry_declared_by' for edge in graph.edges)


def test_trace_failure_never_changes_conversion_result(tmp_path, monkeypatch):
    from runtime.component_conversion import conversion_trace
    def unavailable(*args):
        raise PermissionError('Read-only diagnostic storage')
    monkeypatch.setattr(conversion_trace, '_write', unavailable)
    plan, boundaries, outcomes, blockers = records()
    config = SimpleNamespace(run_id='run', output_root=str(tmp_path / 'generated'))
    assert conversion_trace.record_trace(config, tmp_path, plan, boundaries, {}, outcomes) is None
    assert conversion_trace.record_blocker(config, SimpleNamespace(fingerprint='plan'), 'main', 'prerequisite', 'reason') is None


def test_old_success_snapshot_cannot_override_new_converter_failure(tmp_path):
    save_graph(tmp_path, graph_fixture())
    stage = tmp_path / 'reports/3_dependency_closure_and_component_conversion'
    stage.mkdir(parents=True)
    (stage / 'component-generation.json').write_text(json.dumps(dict(groups={'main': dict(status='failed')})))
    with pytest.raises(ValueError, match='predates the current component report'):
        load_graph(tmp_path)


def test_failed_resume_cannot_present_a_previous_graph_as_current(tmp_path):
    graph = graph_fixture()
    graph.recorded_at = '2026-01-01T00:00:00+00:00'
    save_graph(tmp_path, graph)
    (tmp_path / 'state/run_activity.json').write_text(json.dumps(dict(last_resumed_at='2026-01-02T00:00:00+00:00')))
    with pytest.raises(ValueError, match='newer resume'):
        load_graph(tmp_path)


def test_analyzer_retains_inheritance_and_superclass_field_evidence(boundary_tool):
    from tools.behavior_verification.boundaries import build_boundary_report
    value = unit('response_format', 'example.Child', [
        source('context', 'package com.ibm.dse.base; public class Context {}'),
        source('parent', 'package example; public class Parent { private Helper helper; public String format(com.ibm.dse.base.Context context){return "";} }'),
        source('child', 'package example; public class Child extends Parent {}'),
        source('helper', 'package example; public class Helper extends HelperBase {}'),
        source('helper-base', 'package example; public class HelperBase {}')])
    value['effective_configuration']['children'][0]['decorators'] = []
    report = build_boundary_report(prepared(value), tool_jar=boundary_tool)
    boundary = next(iter(report['boundaries'].values()))
    assert boundary['analysis_status'] == 'identified', boundary['issues']
    assert boundary['legacy_method']['declaring_class'] == 'example.Parent'
    classes = {item['name']: item for item in report['diagnostic_structure'][value['unit_id']]['classes']}
    assert dict(name='example.Parent', relation='extends') in classes['example.Child']['parents']
    assert dict(name='helper', type='example.Helper') in classes['example.Parent']['fields']
    assert dict(name='example.HelperBase', relation='extends') in classes['example.Helper']['parents']
    assert boundary['verification_status'] == 'not_run'
