"""Exercise real-progress timeouts and explicit boundary failure propagation."""
import subprocess
import sys
from types import SimpleNamespace

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope, boundary_analysis_inactivity_timeout
from runtime.java_process_activity import run_with_activity_timeout
from runtime.component_conversion.analysis_failures import (ComponentAnalysisBlocked,
    require_analysis, require_prerequisites, failure_result)
from tools.behavior_verification.analysis_activity import AnalysisActivity
from tools.behavior_verification.analysis_failure import BoundaryAnalysisFailure
from tools.behavior_verification.analysis_progress import run_with_progress
from tools.behavior_verification.boundaries import build_boundary_report
from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy
from test_behavior_verification_boundaries import prepared, unit


def test_only_advancing_work_resets_activity():
    activity = AnalysisActivity()
    assert activity.observe('Boundary progress +1.0s: reachable node code-1')
    assert not activity.observe('Boundary progress +5.0s: reachable node code-1')
    assert not activity.observe('Boundary progress +6.0s: slow operation code-1; operation elapsed=6; stack=working')
    assert not activity.observe('Boundary analyzer running: 10s elapsed')
    assert not activity.observe('arbitrary output')
    assert activity.observe('Boundary progress +8.0s: XML output bytes=10; destination writes=1')
    assert not activity.observe('Boundary progress +9.0s: XML output bytes=10; destination writes=2')
    assert activity.observe('Boundary progress +10.0s: XML output bytes=20; destination writes=3')
    assert activity.observe('Boundary progress +11.0s: node complete code-1')
    assert activity.observe('Boundary progress +12.0s: entry next resolving example.Work.execute')
    assert activity.observe('Boundary progress +13.0s: reachable node code-1')
    assert not activity.observe('Boundary progress +14.0s: reachable node code-1')


def run_script(tmp_path, script, **kwargs):
    return run_with_progress([sys.executable, '-u', '-c', script], tmp_path / 'progress.log',
        run_with_activity_timeout, inactivity_timeout_seconds=1, **kwargs)


def test_real_progress_can_exceed_total_window(tmp_path):
    script = "import time; [(print(f'Boundary progress +{i}.0s: reachable node code-{i}',flush=True),time.sleep(.2)) for i in range(9)]"
    assert run_script(tmp_path, script).returncode == 0


@pytest.mark.parametrize('stage', ['slow operation code-1; operation elapsed={i}; stack=working', 'reachable node code-1', 'XML output bytes=1; destination writes={i}'])
def test_heartbeat_or_repeated_stage_does_not_keep_process_alive(tmp_path, stage, monkeypatch):
    processes = []
    launch = subprocess.Popen
    def track(*args, **kwargs):
        process = launch(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(subprocess, 'Popen', track)
    script = "import time; [(print('Boundary progress +%s.0s: ' % i + " + repr(stage) + ".format(i=i),flush=True),time.sleep(.1)) for i in range(100)]"
    with pytest.raises(BoundaryAnalysisFailure) as caught:
        run_script(tmp_path, script)
    details = caught.value.details
    assert details['inactive_seconds'] >= 1
    assert details['elapsed_seconds'] < 5
    assert details['last_diagnostic'].startswith('Boundary progress')
    assert processes[0].poll() is not None
    assert processes[0].stdout.closed and processes[0].stderr.closed


def test_growing_xml_without_console_progress_keeps_process_alive(tmp_path):
    output = tmp_path / 'output.xml'
    script = "import pathlib,time; p=pathlib.Path(" + repr(str(output)) + "); [(p.write_bytes(b'x'*(i+1)),time.sleep(.2)) for i in range(9)]"
    assert run_script(tmp_path, script, output_path=output).returncode == 0


def test_touching_unchanged_xml_does_not_reset_inactivity(tmp_path):
    output = tmp_path / 'output.xml'
    script = "import pathlib,time; p=pathlib.Path(" + repr(str(output)) + "); p.write_bytes(b'x'); [(p.touch(),time.sleep(.1)) for i in range(100)]"
    with pytest.raises(BoundaryAnalysisFailure):
        run_script(tmp_path, script, output_path=output)


def test_timeout_is_run_scoped_without_invalidating_conversion_policy(monkeypatch):
    monkeypatch.setattr('runtime.java_toolchain.resolve_java_home', lambda *_: 'jdk')
    profile = PipelineConfiguration(java_home='jdk', boundary_analysis_inactivity_timeout_seconds=7)
    before = conversion_policy(profile)
    with java_scope(profile):
        assert boundary_analysis_inactivity_timeout() == 7
    assert boundary_analysis_inactivity_timeout() == 300
    profile.boundary_analysis_inactivity_timeout_seconds = 13
    assert conversion_policy(profile) == before
    with pytest.raises(ValueError):
        PipelineConfiguration(boundary_analysis_inactivity_timeout_seconds=0)


def test_boundary_failure_links_components_and_dependencies(monkeypatch):
    def fail(*args, **kwargs):
        raise BoundaryAnalysisFailure('Converter boundary analysis inactivity timeout', output_bytes=123)
    monkeypatch.setattr('tools.behavior_verification.boundaries.analyze_entries', fail)
    boundaries = build_boundary_report(prepared(unit()))
    cause = boundaries['analysis_failures'][0]
    assert boundaries['boundaries']['unit-configured_step']['analysis_failure_id'] == cause['id']
    group = SimpleNamespace(members=['work'], dependencies=[], group_id='work-group')
    plan = SimpleNamespace(components={'work': SimpleNamespace(unit_ids=['unit-configured_step'])})
    with pytest.raises(ComponentAnalysisBlocked) as caught:
        require_analysis(plan, group, boundaries)
    result = failure_result(group, caught.value)
    assert result['root_cause_ids'] == [cause['id']]
    assert result['failure_role'] == 'analysis_consequence'
    dependent = SimpleNamespace(members=['shared'], dependencies=['work-group'])
    with pytest.raises(ComponentAnalysisBlocked) as caught:
        require_prerequisites(dependent, {'groups': {'work-group': result}})
    assert failure_result(dependent, caught.value)['failure_role'] == 'dependency_consequence'
    unrelated = failure_result(dependent, ValueError('1 validation error for SharedFixtureBank'))
    assert 'root_cause_ids' not in unrelated
    assert 'failure_role' not in unrelated


def test_analysis_failure_reaches_request_and_saved_component_result(tmp_path, monkeypatch):
    import json
    from test_component_graph import origin, step, operation
    from tools.conversion_tools.component_graph import build_component_plan
    from tools.conversion_tools.component_identity import component_group
    from tools.state_store_tools.db import get_connection, create_all_tables
    from tools.state_store_tools.runs import upsert_run
    from runtime.component_conversion.requests import build_component_request
    from runtime.component_conversion.runner import convert_basic_components
    text = 'package example; public class Work { public int execute(){return 7;} }'
    original = origin('example.Work', text=text)
    path = tmp_path / 'Work.java'
    path.write_text(text, encoding='utf-8')
    original[0]['source_file'] = str(path)
    prepared_unit = step()
    preparation = dict(operations={'BANK/Op': operation([prepared_unit], [original])})
    plan = build_component_plan(preparation['operations'])
    preparation['component_plan'] = plan.model_dump(mode='json')
    def fail(*args, **kwargs):
        raise BoundaryAnalysisFailure('Converter boundary analysis inactivity timeout after 300 seconds without meaningful progress')
    monkeypatch.setattr('tools.behavior_verification.boundaries.analyze_entries', fail)
    boundaries = build_boundary_report(preparation)
    cause = boundaries['analysis_failures'][0]
    component = next(key for key, node in plan.components.items() if node.label == 'example.Work')
    group = component_group(plan, component)
    profile = PipelineConfiguration(source_root=str(tmp_path), java_version=25,
        conversion_strategy='behavior_units', scoped_native_mode='component_first_v1',
        executable_verification=dict(mode='test_based_v1'))
    with pytest.raises(ComponentAnalysisBlocked, match='underlying analysis failure'):
        build_component_request(plan, group, boundaries, [], profile, units={prepared_unit['unit_id']: prepared_unit})
    monkeypatch.setattr('runtime.component_conversion.runner.build_boundary_report', lambda *a, **k: boundaries)
    monkeypatch.setattr('runtime.component_conversion.scope.validate_checkpoints', lambda *a, **k: None)
    config = SimpleNamespace(run_id='analysis-fixture', output_root=str(tmp_path / 'output'), source_root=str(tmp_path))
    conn = get_connection(str(tmp_path / 'state.db'))
    try:
        create_all_tables(conn)
        upsert_run(conn, run_id=config.run_id, run_mode='conversion')
        directory = tmp_path / 'run'
        convert_basic_components(conn, config, profile, directory, preparation, None, include_steps=True,
            model_call=lambda *a: pytest.fail('No generation without analysis'))
        saved = json.loads((directory / 'reports/3_dependency_closure_and_component_conversion/component-generation.json').read_text())
        assert saved['analysis_failures'] == [cause]
        result = saved['groups'][group.group_id]
        assert result['failure_role'] == 'analysis_consequence'
        assert result['root_cause_ids'] == [cause['id']]
        assert 'no parser-backed entry' not in result['reason']
        assert any(item.get('failure_role') == 'dependency_consequence' for item in saved['groups'].values())
        assert conn.execute('SELECT count(*) FROM behavior_attempts').fetchone()[0] == 0
    finally:
        conn.close()
