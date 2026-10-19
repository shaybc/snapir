"""Replay the latest oversized route-test correction without changing its saved run."""

from copy import deepcopy
import json
from pathlib import Path

from agents.behavior_conversion.operation_route_tests import SCENARIO
from runtime.behavior_conversion.request_context import encode_request
from runtime.behavior_conversion.test_feedback import TEST_CORRECTION_INSTRUCTION
from runtime.behavior_conversion.generation import generate
from models.native_unit_bundle import NativeUnitBundle
from tests.runtime.test_behavior_conversion import state, profile


def replay_payload(tmp_path):
    """Use frozen accepted step sources instead of reading the live migration."""
    payload = json.loads((Path(__file__).parent / 'fixtures/latest_route_test_correction_budget.json').read_text())
    shared = json.loads((Path(__file__).parent / 'fixtures/latest_route_step_sources.json').read_text())
    for key, unit in payload['accepted_units'].items():
        unit['project'] = str(tmp_path / key)
        for path, content in shared.get(key, {}).items():
            target = Path(unit['project']) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
    return payload


def test_latest_route_failure_fits_and_preserves_mock_side_effect_evidence(tmp_path):
    payload = replay_payload(tmp_path)
    original = deepcopy(payload)
    instruction = SCENARIO + TEST_CORRECTION_INSTRUCTION
    assert len(json.dumps(payload)) + len(instruction) > 180000
    request, encoded = encode_request(payload, instruction, 180000)
    assert len(encoded) + len(instruction) <= 180000
    assert payload == original
    correction = request['test_correction']
    assert correction['diagnostics'] == payload['test_correction']['diagnostics']
    assert correction['failed_sources'] == payload['test_correction']['failed_sources']
    sources = {Path(item['path']).stem: item['content'] for item in correction['relevant_implementation_sources']}
    assert 'context.put("ErrorCategory"' in sources['TechnicalErrorStep']
    assert 'context.containsKey("ErrorCategory")' in sources['TransferFundsOpService']
    assert request['scenario'] == payload['scenario']
    assert request['operation_contract'] == payload['operation_contract']
    assert request['closure']['routing_graph'] == payload['closure']['routing_graph']
    for key, unit in request['accepted_units'].items():
        assert unit['apis'] == payload['accepted_units'][key]['apis']
        assert unit['public_api'] == payload['accepted_units'][key]['public_api']


def test_trimmed_latest_correction_reaches_model_and_preserves_raw_response(tmp_path):
    payload = replay_payload(tmp_path)
    response = payload['previous_model_response']
    conn, config = state()
    calls = []
    def model(instruction, encoded):
        calls.append(json.loads(encoded))
        assert len(encoded) + len(instruction) <= 180000
        assert calls[-1]['test_correction']['failed_sources'] == payload['test_correction']['failed_sources']
        return response
    generate(conn, config, profile(java_version=25, behavior_context_chars=180000),
        'route_scenario_test', 'saved-failure', SCENARIO, payload, NativeUnitBundle,
        model_call=model, require_coverage=False)
    assert len(calls) == 1
    assert conn.execute('SELECT response FROM behavior_attempts').fetchone()[0] == response


def test_direct_call_selection_is_generic_and_does_not_follow_unrelated_dependencies():
    from runtime.behavior_conversion.test_correction_payload import trim_test_correction
    correction = {'diagnostics': [], 'failed_sources': [{'path': 'src/test/java/Case.java',
        'content': 'class Case { void test() { Worker worker = mock(Worker.class); worker.run(); } }'}],
        'relevant_implementation_sources': [{'path': 'src/main/java/Worker.java', 'content': 'class Worker { Helper helper; void run() {} }'},
            {'path': 'src/main/java/Helper.java', 'content': 'class Helper {}'}]}
    result = trim_test_correction({'test_correction': correction})
    assert [item['path'] for item in result['test_correction']['relevant_implementation_sources']] == ['src/main/java/Worker.java']
