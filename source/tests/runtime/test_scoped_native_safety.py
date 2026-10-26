"""Verify qualified task boundaries, exact reuse, and occurrence-preserving requests."""

from copy import deepcopy
from pathlib import Path

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope, resolve_java_home
from runtime.scoped_native.payloads import native_inputs
from runtime.scoped_native.scope import native_execution, require_task
from runtime.behavior_conversion.generation import generate, EvidenceSummary
from tools.conversion_tools.scoped_workflow.preparation import prepare_scoped_workflow
from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.behavior_units import initialize
from tests.runtime.test_scoped_native import scoped_state, scoped_mapper


@pytest.fixture(scope='module')
def prepared(tmp_path_factory, scoped_mapper):
    folder = tmp_path_factory.mktemp('scoped-native-safety')
    conn, config = scoped_state(folder, scoped_mapper)
    profile = PipelineConfiguration(source_root=config.source_root, scoped_java_project='.', scoped_native_mode='behavior_units_v1',
        conversion_strategy='behavior_units', java_version=25, java_home=resolve_java_home(25), model_provider='mock',
        classpath_jars=[], eclipse_classpath_variables={}, max_agent_task_retries=1)
    with java_scope(profile):
        classpath = discover_java_classpath(config.source_root, [], {})
        report = prepare_scoped_workflow(conn, config, profile, classpath_index=classpath)
    assert all(item['status'] == 'prepared' for item in report['operations'].values()), report
    initialize(conn)
    yield conn, config, profile, classpath, report
    conn.close()


@pytest.fixture
def isolated(prepared):
    original, config, profile, classpath, report = prepared
    conn = get_connection(':memory:')
    original.backup(conn)
    source = Path(config.source_root) / 'src/example/Work.java'
    before = source.read_bytes()
    yield conn, config, profile, classpath, deepcopy(report)
    source.write_bytes(before)
    conn.close()


def test_payload_preserves_repeats_and_canonical_evidence(prepared):
    _, _, profile, _, report = prepared
    closures, own, units, bindings = native_inputs(report)
    workflow = closures[0]['scoped_workflow']
    assert [step['business_name'] for step in workflow['steps']] == ['Repeat', 'Repeat']
    occurrences = [step['occurrence_id'] for step in workflow['steps']]
    assert len(set(occurrences)) == 2 and set(bindings['XML/Flow']) == set(occurrences)
    assert workflow['routing_graph'][occurrences[0]] == {'on0Do': occurrences[1]}
    assert workflow['routing_graph'][occurrences[1]] == {'on0Do': 'end'}
    assert workflow['source_routing_graph'] == report['operations']['XML/Flow']['behavior_request']['routing_graph']
    reordered = deepcopy(report)
    request = reordered['operations']['XML/Flow']['behavior_request']
    request['unit_bindings'] = dict(reversed(list(request['unit_bindings'].items())))
    assert list(native_inputs(reordered)[3]['XML/Flow']) == occurrences
    from runtime.behavior_conversion.service_flow import service_request
    payload = service_request(profile, closures[0], None, {})
    assert 'operation-flow' in payload['requirements']
    assert not report['operations']['XML/Flow']['behavior_request']['conversion_enabled']


def test_backward_and_self_routes_and_body_switches_are_retained(prepared):
    report = deepcopy(prepared[-1])
    item = report['operations']['XML/Flow']['behavior_request']
    first, second = item['steps']
    first['routes'] = {'on0Do': first['note'], 'on1Do': second['note']}
    second['routes'] = {'on0Do': first['note'], 'onOtherDo': None}
    second['return_body_switches'] = {'onOtherReturn': 'qualified-format'}
    closures, *_ = native_inputs(report)
    workflow = closures[0]['scoped_workflow']
    assert workflow['routing_graph'][first['occurrence_id']]['on0Do'] == first['occurrence_id']
    assert workflow['routing_graph'][second['occurrence_id']]['on0Do'] == first['occurrence_id']
    assert workflow['steps'][1]['return_body_switches'] == {'onOtherReturn': 'qualified-format'}


def test_unselected_route_and_unit_context_cannot_be_adapted(prepared):
    report = deepcopy(prepared[-1])
    report['operations']['XML/Flow']['behavior_request']['steps'][0]['routes']['on0Do'] = 'unselected.md'
    with pytest.raises(ValueError, match='outside selected'):
        native_inputs(report)
    report = deepcopy(prepared[-1])
    report['operations']['XML/Flow']['units'][0]['operation_identity'] = 'alien'
    with pytest.raises(ValueError, match='consuming context'):
        native_inputs(report)


def test_guard_only_permits_selected_tasks_within_the_current_invocation(isolated):
    conn, config, profile, classpath, report = isolated
    _, own, units, _ = native_inputs(report)
    identity = next(iter(units))
    with pytest.raises(ValueError, match='gated'):
        require_task(conn, config, profile, 'unit', identity, {})
    with native_execution(conn, config, profile, classpath, own):
        assert require_task(conn, config, profile, 'unit', identity, {})[1] == 'XML/Flow'
        with pytest.raises(ValueError, match='outside the selected'):
            require_task(conn, config, profile, 'unit', 'another-context', {})
        with pytest.raises(ValueError, match='Unsupported'):
            require_task(conn, config, profile, 'legacy-conversion', identity, {})
    with pytest.raises(ValueError, match='gated'):
        require_task(conn, config, profile, 'unit', identity, {})


def test_result_reuse_requires_exact_request_and_never_calls_legacy_compatibility(isolated, monkeypatch):
    conn, config, profile, classpath, report = isolated
    _, own, units, _ = native_inputs(report)
    identity = next(iter(units))
    requests = []
    def model(*args):
        requests.append(args)
        return '{"findings":["verified configuration"]}'
    def legacy(*args):
        pytest.fail('Scoped results consulted legacy compatibility')
    monkeypatch.setattr('runtime.behavior_conversion.compatibility.accepted_compatibility', legacy)
    with native_execution(conn, config, profile, classpath, own):
        for payload in ({'query': 'same', 'facts': {'first': 1, 'second': 2}},
                        {'facts': {'second': 2, 'first': 1}, 'query': 'same'},
                        {'query': 'different', 'facts': {'first': 1, 'second': 2}}):
            generate(conn, config, profile, 'analysis', identity, 'Inspect', payload, EvidenceSummary, model_call=model)
    assert len(requests) == 2


def test_changed_source_blocks_before_model_call(isolated):
    conn, config, profile, classpath, report = isolated
    _, own, units, _ = native_inputs(report)
    source = Path(config.source_root) / 'src/example/Work.java'
    with native_execution(conn, config, profile, classpath, own):
        source.write_bytes(source.read_bytes() + b'\n// changed\n')
        with pytest.raises(ScopedCheckpointStale):
            generate(conn, config, profile, 'analysis', next(iter(units)), 'Inspect', {}, EvidenceSummary,
                model_call=lambda *args: pytest.fail('Changed source reached model'))


def test_source_is_rechecked_after_the_validator(isolated):
    conn, config, profile, classpath, report = isolated
    _, own, units, _ = native_inputs(report)
    def change(output, cached=False):
        source = Path(config.source_root) / 'src/example/Work.java'
        source.write_bytes(source.read_bytes() + b'\n// changed by validation\n')
    with native_execution(conn, config, profile, classpath, own):
        with pytest.raises(ScopedCheckpointStale):
            generate(conn, config, profile, 'analysis', next(iter(units)), 'Inspect', {}, EvidenceSummary,
                validator=change, model_call=lambda *args: '{"findings":["candidate"]}')
    assert conn.execute("SELECT count(*) FROM scoped_reuse_entries WHERE category='result'").fetchone()[0] == 0


def test_generated_artifact_coordinate_does_not_rename_operation_identity():
    from runtime.scoped_native.project_names import native_artifact_id
    assert native_artifact_id('Flow') == 'Flow'
    assert native_artifact_id('#Flow').startswith('scoped-')
    assert native_artifact_id('#Flow') != native_artifact_id('%23Flow')


def test_dependency_advice_normalization_preserves_business_configuration():
    from runtime.scoped_native.results import fingerprint_payload
    payload = dict(known_dependencies=['derived'], unit=dict(unit_id='one', known_dependencies=['derived'],
        effective_configuration={'attributes': {'known_dependencies': 'business value'}}))
    result = fingerprint_payload(payload, 'review')
    assert 'known_dependencies' not in result and 'known_dependencies' not in result['unit']
    assert result['unit']['effective_configuration']['attributes']['known_dependencies'] == 'business value'
    assert fingerprint_payload(payload, 'analysis') == payload
    assert payload['known_dependencies'] == ['derived']


def test_plan_approval_is_content_bound_and_separate_from_native_gates(isolated, tmp_path):
    from runtime.scoped_native.runner import _execution_plan
    from runtime.scoped_native.plan_approval import approve_plan
    from runtime.intake_plan import record_plan_decision, has_intake_plan
    from runtime.workspace_paths import run_report_path
    conn, config, profile, _, report = isolated
    closures, _, _, _ = native_inputs(report)
    plan = _execution_plan(conn, config, closures, None)
    with java_scope(profile):
        assert not approve_plan(conn, config, profile, tmp_path, plan)
        assert conn.execute('SELECT current_phase FROM runs').fetchone()[0] == 'conversion_plan_pending'
        assert not has_intake_plan(conn, config.run_id)
        record_plan_decision(conn, config, profile, tmp_path, 'approved')
        assert approve_plan(conn, config, profile, tmp_path, plan)
        displayed = run_report_path(tmp_path, 'conversion_plan.md')
        displayed.write_text('tampered', encoding='utf-8')
        with pytest.raises(ValueError, match='changed'):
            record_plan_decision(conn, config, profile, tmp_path, 'approved')
