"""Verify real Maven validation is retained when a second run skips AI implementation."""
import json
import shutil
from types import SimpleNamespace
from pathlib import Path
import pytest

from test_component_generation import boundary_tool, native_fixture, PRIMITIVES
from test_component_graph import origin, step, operation
from runtime.component_conversion.runner import _convert_group
from runtime.component_conversion.scope import component_execution
from tests.runtime.test_scoped_native import actual_build
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.component_identity import component_group
from tools.behavior_verification.boundaries import build_boundary_report
from models.pipeline_configuration import PipelineConfiguration


@pytest.fixture(params=['checklist_v1', 'test_based_v1'])
def component_case(tmp_path, boundary_tool, monkeypatch, request):
    # Other JVM regression modules rebuild the tool JAR. Keep this long reuse
    # experiment on one tool revision, so relocation is the only changing input.
    pinned_tool = tmp_path / 'analysis-tool.jar'
    shutil.copyfile(boundary_tool, pinned_tool)
    folder = tmp_path / 'original'
    folder.mkdir()
    original, text = origin('example.Primitives', text=PRIMITIVES)
    source = folder / 'Primitives.java'
    source.write_text(text, encoding='utf-8', newline='\n')
    original['source_file'] = str(source)
    operations = {'XML/Flow': operation([step(implementation='example.Primitives')], [(original, text)])}
    plan = build_component_plan(operations)
    preparation = dict(operations=operations, component_plan=plan.model_dump(mode='json'))
    boundaries = build_boundary_report(preparation, tool_jar=pinned_tool, collect_checklists=request.param!='test_based_v1')
    key = next(key for key, node in plan.components.items() if node.kind == 'java_implementation')
    conn = get_connection(str(tmp_path / 'state.db'))
    create_all_tables(conn)
    config = SimpleNamespace(run_id='first-operation', output_root=str(tmp_path / 'output'), source_root=str(folder), analysis_tool=pinned_tool)
    upsert_run(conn, run_id=config.run_id, run_mode='conversion')
    profile = PipelineConfiguration(source_root=str(folder), source_workspace_id='cross-run-fixture',
        shared_store_root=str(tmp_path / 'shared'), conversion_strategy='behavior_units',
        scoped_native_mode='component_first_v1', staged_unit_conversion=request.param=='test_based_v1', java_version=25,
        executable_verification={'mode':request.param})
    monkeypatch.setattr('runtime.component_conversion.scope.validate_checkpoints', lambda *args: None)
    yield conn, config, profile, preparation, plan, component_group(plan, key), boundaries
    conn.close()


def test_new_run_reuses_approved_base_component(component_case, tmp_path):
    conn, first, profile, preparation, plan, group, _ = component_case
    profile.shared_store_root = str(tmp_path / 'shared')
    calls = []
    boundaries = component_case[-1]
    staged = profile.executable_verification.mode == 'test_based_v1'
    if staged:
        from runtime.component_conversion.requests import build_component_request
        request, _ = build_component_request(plan, group, boundaries, [], profile)
        fixture = native_fixture(request)
    def model(instruction, encoded):
        request = json.loads(encoded)
        calls.append(request)
        if staged:
            title = request['schema']['title']
            if title == 'NativeImplementation':
                return json.dumps(dict(files=[f for f in fixture['files'] if f['path'].startswith('src/main/')]))
            if title == 'NativeComponentDetails':
                return json.dumps(dict(component_details=dict(configuration_parameters={'pattern':'String'},
                    runtime_inputs={'channel':'String','application':'String','settings':'Set<String>'})))
            if title == 'NativeTestBundle':
                return json.dumps(dict(files=[f for f in fixture['files'] if f['path'].startswith('src/test/')], coverage=fixture['coverage']))
            pytest.fail('Unexpected generation stage: ' + title)
        return json.dumps(native_fixture(request))
    def convert(config, callback):
        units = {unit['unit_id']: unit for item in preparation['operations'].values() for unit in item['units']}
        with component_execution(conn, config, profile, None, preparation, include_steps=True):
            return _convert_group(conn, config, profile, plan, group, boundaries,
                                  Path(config.output_root) / 'components', actual_build, callback, units=units)
    assert not convert(first, model)['reused']
    expected_calls = 3 if staged else 1
    assert len(calls) == expected_calls
    second = SimpleNamespace(run_id='another-operation-run', output_root=str(tmp_path / 'another-output'), source_root=first.source_root)
    upsert_run(conn, run_id=second.run_id, run_mode='conversion')
    result = convert(second, lambda *args: (_ for _ in ()).throw(AssertionError('Repeated AI generation')))
    assert result['status'] == 'component_validated' and result['reused'], result
    assert conn.execute('SELECT count(*) FROM shared_component_uses WHERE run_id=?', (second.run_id,)).fetchone()[0] == 1
    from tools.state_store_tools.component_reuse import group_uses
    from tools.shared_artifact_store.storage import ArtifactStore
    pinned = group_uses(conn, second.run_id)[group.group_id]
    with ArtifactStore(profile.shared_store_root, 'components') as store:
        directory, manifest = store.find(pinned['lookup_key'], revision=pinned['revision'])
    jar = directory / manifest['metadata']['jar']
    assert jar.resolve().is_relative_to(tmp_path.resolve())
    jar.unlink()
    (Path(profile.shared_store_root) / 'components/registry.db').unlink()
    third = SimpleNamespace(run_id='recovered-operation-run', output_root=str(tmp_path / 'recovered-output'), source_root=first.source_root)
    upsert_run(conn, run_id=third.run_id, run_mode='conversion')
    recovered = convert(third, lambda *args: (_ for _ in ()).throw(AssertionError('Recovery requested AI generation')))
    assert recovered['reused'] and len(calls) == expected_calls
    assert conn.execute('SELECT decision FROM shared_component_decisions WHERE run_id=?', (third.run_id,)).fetchone()[0] == 'rebuilt'
    recovered_key = group_uses(conn, third.run_id)[group.group_id]['lookup_key']
    relocated_source = tmp_path / 'relocated-original'
    Path(first.source_root).rename(relocated_source)
    for operation in preparation['operations'].values():
        for original in operation['behavior_request']['java_origins']:
            if original.get('source_file'):
                original['source_file'] = str(relocated_source / Path(original['source_file']).name)
    profile.source_root = str(relocated_source)
    plan = build_component_plan(preparation['operations'])
    key = next(key for key, node in plan.components.items() if node.kind == 'java_implementation')
    group = component_group(plan, key)
    preparation['component_plan'] = plan.model_dump(mode='json')
    boundaries = build_boundary_report(preparation, tool_jar=first.analysis_tool, collect_checklists=not staged)
    fourth = SimpleNamespace(run_id='relocated-source-run', output_root=str(tmp_path / 'relocated-output'), source_root=str(relocated_source))
    upsert_run(conn, run_id=fourth.run_id, run_mode='conversion')
    result = convert(fourth, lambda *args: (_ for _ in ()).throw(AssertionError('Relocation requested AI generation')))
    assert result['reused'] and len(calls) == expected_calls
    assert group_uses(conn, fourth.run_id)[group.group_id]['lookup_key'] == recovered_key


def test_source_relocation_keeps_shared_request_identity(component_case, tmp_path):
    from runtime.component_conversion.requests import build_component_request
    from runtime.component_conversion.shared_identity import request_identity
    _, config, profile, preparation, plan, group, boundaries = component_case
    first, _ = build_component_request(plan, group, boundaries, [], profile)
    relocated = tmp_path / 'relocated-original'
    Path(config.source_root).rename(relocated)
    for operation in preparation['operations'].values():
        for original in operation['behavior_request']['java_origins']:
            if original.get('source_file'):
                original['source_file'] = str(relocated / Path(original['source_file']).name)
    profile.source_root = str(relocated)
    plan = build_component_plan(preparation['operations'])
    key = next(key for key, node in plan.components.items() if node.kind == 'java_implementation')
    group = component_group(plan, key)
    preparation['component_plan'] = plan.model_dump(mode='json')
    boundaries = build_boundary_report(preparation, tool_jar=config.analysis_tool, collect_checklists=profile.executable_verification.mode!='test_based_v1')
    second, _ = build_component_request(plan, group, boundaries, [], profile)
    assert request_identity(first, profile) == request_identity(second, profile), {
        key:(first.get(key), second.get(key)) for key in first.keys() | second.keys() if first.get(key)!=second.get(key)}
