"""Standalone component selection reuses generation and exact inherited entry contracts."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.component_conversion.standalone_preparation import prepare_components, verify_preparation
from runtime.component_conversion.requests import build_component_request
from tools.conversion_tools.component_identity import checked_plan
from test_behavior_verification_boundaries import boundary_tool


@pytest.fixture
def workspace(tmp_path):
    files = {
        'com/ibm/dse/base/Context.java': '''package com.ibm.dse.base; import java.util.*;
public class Context {private final Map<String,Object> values=new LinkedHashMap<>();
public Object getValueAt(String key){return values.get(key);} public void setValueAt(String key,Object value){values.put(key,value);}
public Object removeValueAt(String key){return values.remove(key);} public Map<String,Object> snapshot(){return values;}}''',
        'com/ibm/dse/base/DataElement.java': 'package com.ibm.dse.base; public class DataElement {}',
        'com/ibm/dse/base/FormatElement.java': 'package com.ibm.dse.base; public abstract class FormatElement {}',
        'example/BaseFormat.java': '''package example; import com.ibm.dse.base.Context;
public class BaseFormat extends com.ibm.dse.base.FormatElement { public void setDataName(String name){} public String format(Context context){return "<value/>";}
public com.ibm.dse.base.DataElement unformat(String xml,Context context){return null;} }''',
        'example/CCString.java': 'package example; public class CCString extends BaseFormat {}',
        'example/OtherFormat.java': 'package example; public class OtherFormat extends BaseFormat {}',
        'example/Step.java': '''package example; import com.ibm.dse.base.Context;
public class Step {public void setContext(Context context){} public int execute(){return 0;}}''',
        'example/ChildStep.java': 'package example; public class ChildStep extends Step {}',
        'example/Unrelated.java': 'package example; public class Unrelated {}',
        'example/MethodLookalike.java': 'package example; public class MethodLookalike { public String format(){return "";} public void unformat(){} }',
        'other/WildcardFormat.java': 'package other; import example.*; public class WildcardFormat extends BaseFormat {}',
    }
    for name, text in files.items():
        path = tmp_path / 'src/main/java' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    return tmp_path


def profile(root, names=None, kind='format', **kwargs):
    return PipelineConfiguration(source_root=str(root), conversion_scope='components', component_type=kind,
        selected_components=names or ['example.CCString'], channels=[], conversion_strategy='behavior_units',
        scoped_native_mode='component_first_v1', java_version=25, cross_run_component_reuse=False,
        executable_verification={'mode': 'test_based_v1', 'random_cases': 0}, **kwargs)


def test_scope_validation_and_old_profile_defaults(workspace):
    assert PipelineConfiguration().conversion_scope == 'operations'
    with pytest.raises(ValidationError, match='channels'):
        PipelineConfiguration(channels=[])
    with pytest.raises(ValidationError, match='selected_components'):
        PipelineConfiguration(conversion_scope='components', component_type='format')
    value = profile(workspace, ['example.CCString', 'example.OtherFormat'])
    assert PipelineConfiguration.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError, match='unique'):
        profile(workspace, ['example.CCString', 'example.CCString'])


def test_catalog_lists_inherited_formats_and_steps(workspace, boundary_tool):
    from tools.conversion_tools.standalone_sources import component_catalog
    with java_scope(PipelineConfiguration(java_version=25)):
        found = component_catalog(workspace)
    assert {'example.CCString', 'example.OtherFormat', 'other.WildcardFormat'} <= set(found['format'])
    assert {'example.Step', 'example.ChildStep'} <= set(found['op_step'])
    assert 'example.Unrelated' not in found['format'] + found['op_step']
    assert 'example.MethodLookalike' not in found['format']


@pytest.mark.parametrize('names,kind', [(['example.CCString'], 'format'),
    (['example.CCString', 'example.OtherFormat'], 'format'), (['example.ChildStep'], 'op_step')])
def test_prepare_and_request_use_own_inherited_entries(workspace, boundary_tool, names, kind):
    selected = profile(workspace, names, kind)
    with java_scope(selected):
        preparation, _ = prepare_components(selected)
        assert not preparation['operations']
        assert preparation['boundaries']['counts']['incomplete'] == 0, preparation['boundaries']
        units = {unit['unit_id']: unit for unit in preparation['standalone_units']}
        assert len(units) == len(names) * (2 if kind == 'format' else 1)
        assert not any('Unrelated' in origin['fqcn'] for origin in preparation['java_origins'])
        plan = checked_plan(preparation['component_plan'])
        for group in plan.groups:
            request, _ = build_component_request(plan, group, preparation['boundaries'], [], selected, units=units)
            expected = ['example.BaseFormat.format(com.ibm.dse.base.Context)', 'example.BaseFormat.unformat(java.lang.String, com.ibm.dse.base.Context)'] if kind == 'format' else ['example.Step.execute()']
            assert next(iter(request['source_entry_points'].values())) == expected
            assert set(request['standalone_component']['classes']) <= set(names)
            assert not request.get('configured_format') and not request.get('configured_unit')
        verify_preparation(selected, preparation)
        (workspace / 'src/main/java/example/BaseFormat.java').write_text('changed')
        if kind == 'format':
            with pytest.raises(ValueError, match='source changed'):
                verify_preparation(selected, preparation)


def test_missing_direction_blocks_without_borrowing_other_format(workspace, boundary_tool):
    (workspace / 'src/main/java/example/Broken.java').write_text('''package example; import com.ibm.dse.base.Context;
public class Broken extends com.ibm.dse.base.FormatElement {public String format(Context context){return "";}}''')
    selected = profile(workspace, ['example.Broken'])
    with java_scope(selected):
        preparation, _ = prepare_components(selected)
        plan = checked_plan(preparation['component_plan'])
        with pytest.raises(ValueError, match='own identified entry point'):
            build_component_request(plan, plan.groups[0], preparation['boundaries'], [], selected)


def test_component_menu_selects_many_without_channel_discovery(tmp_path, monkeypatch):
    from cli.configuration_flow import collect_section
    from models.configuration_draft import ConfigurationDraft
    draft = ConfigurationDraft(section=3, sections={0: {'source_root': str(tmp_path)}})
    def menu(title, options):
        return 'components' if title == 'Conversion scope' else 'format'
    inputs = SimpleNamespace(menu=menu, multiple=lambda title, options, **kwargs: [value for value, _ in options])
    monkeypatch.setattr('tools.conversion_tools.standalone_sources.component_catalog',
        lambda root, **kwargs: dict(format=['example.One', 'example.Two'], op_step=[]))
    api = SimpleNamespace(discover_channel_directories=lambda *args: pytest.fail('Channel discovery ran'))
    result = collect_section(draft, inputs, tmp_path, api)
    assert result['selected_components'] == ['example.One', 'example.Two']
    assert result['channels'] == result['include_operations'] == []


def test_start_and_resume_route_away_from_operation_pipeline(workspace, monkeypatch):
    from runtime.pipeline_runner import run_pipeline
    from runtime.checkpoints import resume_pipeline
    from runtime.workspace_paths import run_profile_path, run_database_path
    selected = profile(workspace)
    monkeypatch.setattr('runtime.pipeline_runner._run_intake', lambda *args: pytest.fail('Operation intake ran'))
    monkeypatch.setattr('runtime.component_conversion.standalone_components.start_components', lambda *args: 'standalone')
    assert run_pipeline(selected, 'single') == 'standalone'
    directory = workspace / 'single'
    run_profile_path(directory).parent.mkdir(parents=True)
    run_database_path(directory).touch()
    run_profile_path(directory).write_text(selected.model_dump_json())
    monkeypatch.setattr('runtime.component_conversion.standalone_components.resume_components', lambda *args: 'resumed')
    assert resume_pipeline(str(workspace), 'single') == 'resumed'


def test_failed_current_attempt_cannot_report_an_old_success(tmp_path, monkeypatch):
    from runtime.component_conversion.standalone_components import component_results
    from models.component_conversion_plan import ComponentConversionPlan
    from models.planned_conversion_component import PlannedConversionComponent
    from tools.conversion_tools.component_order import order_component_groups
    from tools.conversion_tools.scoped_reuse.fingerprints import digest
    from runtime.workspace_paths import write_run_report
    node = PlannedConversionComponent(component_id='class', kind='java_implementation', label='example.CCString',
        status='source_recorded', unit_ids=['format', 'unformat'])
    plan = ComponentConversionPlan(components={'class': node})
    plan.groups = order_component_groups(plan.components)
    plan.fingerprint = digest(plan.model_dump(mode='json', exclude={'fingerprint'}))
    preparation = dict(component_plan=plan.model_dump(mode='json'), boundaries=dict(boundaries={identity:
        dict(analysis_status='identified', issues=[]) for identity in node.unit_ids}))
    artifact = tmp_path / 'old'; artifact.mkdir()
    (artifact / 'report.json').write_text(json.dumps(dict(standalone_comparisons={identity:
        dict(status='matched') for identity in node.unit_ids})))
    monkeypatch.setattr('tools.state_store_tools.component_records.head', lambda *args: dict(result_revision='old'))
    monkeypatch.setattr('tools.state_store_tools.component_records.read_record', lambda *args: dict(results={
        'class': dict(artifact_root=str(artifact), validation_report='report.json')}))
    config = SimpleNamespace(run_id='test', output_root=str(tmp_path / 'generated'))
    write_run_report(tmp_path, 'component-generation.json', json.dumps(dict(groups={plan.groups[0].group_id:
        dict(status='incomplete', reason='Current signatures changed')})))
    result = component_results(None, config, preparation)
    assert result['status'] == 'blocked'
    assert result['components']['example.CCString']['comparisons'] == {}
    assert result['components']['example.CCString']['reason'] == 'Current signatures changed'


def test_step_context_discovery_and_staged_prompt_keep_selected_scope(tmp_path):
    from runtime.format_comparison.context_discovery import discover_context
    from agents.behavior_conversion.staged_pipeline import code_instruction
    unit = dict(kind='configured_step', sources=[dict(identity='step', content='context.getValueAt("input")')],
        effective_configuration=dict(attributes={'implClass': 'example.Step'}))
    def call(instruction, encoded):
        payload = json.loads(encoded)
        assert payload['execution']['entry_points'] == [dict(direction='step_execute', method_name='execute')]
        return json.dumps(dict(requirements=[dict(requirement_id='input', directions=['step_execute'], context_key='input',
            citations=[dict(source_identity='step', excerpt='context.getValueAt("input")')])]))
    result = discover_context(unit, call, PipelineConfiguration().format_comparison, tmp_path / 'discovery', directions=['step_execute'])
    assert result.requirements[0].directions == ['step_execute'] and not result.unresolved
    prompt = code_instruction(dict(standalone_component=dict(classes=['example.Step'])))
    assert 'Do not generate an operation, channel' in prompt


def test_standalone_run_uses_canonical_generation_and_resumes_without_operations(workspace, boundary_tool, monkeypatch):
    from runtime.component_conversion.standalone_components import start_components, resume_components
    from tools.state_store_tools.db import get_connection
    from tools.state_store_tools.runs import get_run
    from runtime.workspace_paths import run_database_path
    selected = profile(workspace, output_root=str(workspace / 'output'))
    requests = []
    def generate(*args, **kwargs):
        requests.append(args[6])
        raise ValueError('Controlled model fixture stopped before generation')
    monkeypatch.setattr('runtime.component_conversion.runner.generate', generate)
    folder = start_components(selected, 'standalone')
    assert len(requests) == 1
    assert len(next(iter(requests[0]['source_entry_points'].values()))) == 2
    result = json.loads((folder / 'reports/standalone-components.json').read_text())
    assert result['operations_converted'] == 0 and result['status'] == 'blocked'
    assert 'Controlled model fixture' in result['components']['example.CCString']['reason']
    conn = get_connection(str(run_database_path(folder)))
    assert get_run(conn, 'standalone')['status'] == 'blocked'
    conn.close()
    resume_components(selected, folder)
    assert len(requests) == 2 and requests[0]['source_entry_points'] == requests[1]['source_entry_points']


@pytest.mark.parametrize('kind', ['format', 'op_step'])
def test_directional_comparisons_execute_existing_java_engines(workspace, boundary_tool, monkeypatch, kind):
    from runtime.component_conversion.standalone_comparison import compare_standalone
    from models.format_comparison_plan import FormatComparisonEntry
    selected = profile(workspace, ['example.CCString'] if kind == 'format' else ['example.ChildStep'], kind,
        format_comparison={'enabled': True, 'collect_facts': False},
        component_attributes={'example.CCString': {'dataName': 'value'}} if kind == 'format' else {})
    with java_scope(selected):
        preparation, _ = prepare_components(selected)
        units = {unit['unit_id']: unit for unit in preparation['standalone_units']}
        request = dict(standalone_component=dict(boundaries=preparation['boundaries']['boundaries']))
        def bindings(unit, sources, call, settings, directory, **kwargs):
            direction = kwargs['directions'][0]
            return {'entry': FormatComparisonEntry(direction=direction, binding=dict(owner_type='nativecode.StringFormat',
                method_name='execute' if direction == 'step_execute' else direction,
                arguments=[dict(type_name='java.lang.String', source='xml')] if direction == 'unformat' else [],
                output='none' if direction == 'unformat' else 'result'))}, []
        monkeypatch.setattr('runtime.component_conversion.standalone_comparison.propose_bindings', bindings)
        # Keep fixture generation and the real JVM comparison; context discovery makes no model calls here.
        from runtime.format_comparison.preparation import prepare_plan
        monkeypatch.setattr('runtime.component_conversion.standalone_comparison.prepare_plan',
            lambda *args, **kwargs: prepare_plan(*args, **{**kwargs, 'model_call': None}))
        files = {'src/main/java/nativecode/StringFormat.java': '''package nativecode; public class StringFormat {
public String format(){return "<value/>";} public void unformat(String xml){} public int execute(){return 0;} }'''}
        result = compare_standalone(request, units, files, selected, workspace / 'comparisons', model_call=lambda *args: None)
    assert {item['direction'] for item in result.values()} == ({'format', 'unformat'} if kind == 'format' else {'step_execute'})
    assert all(item['status'] == 'matched' for item in result.values()), result
