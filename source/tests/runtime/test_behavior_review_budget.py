"""Replay oversized operation review without regenerating accepted service or tests."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from runtime.behavior_conversion.review import review_behavior
from tools.state_store_tools.behavior_units import save
from tests.runtime.test_behavior_conversion import state, profile


def latest():
    return json.loads((Path(__file__).parent / 'fixtures/latest_behavior_review_budget.json').read_text(encoding='utf-8'))


def execute(payload, budget, responses=None):
    conn, config = state()
    save(conn, config.run_id, 'service', 'operation', 'accepted-service', payload['bundle'])
    tests = [file for file in payload['bundle']['files'] if file['path'].startswith('src/test/java/')]
    for index, file in enumerate(tests):
        save(conn, config.run_id, 'route_scenario_test', str(index), 'accepted-test-' + str(index), file)
    preserved = conn.execute("SELECT * FROM behavior_snapshots WHERE category IN ('service','route_scenario_test') ORDER BY category,identity").fetchall()
    calls = []
    def model(instruction, encoded):
        assert len(instruction) + len(encoded) <= budget
        request = json.loads(encoded)
        assert request['schema']['title'] == 'BehaviorReview'
        calls.append(request)
        return json.dumps(responses[len(calls) - 1] if responses and len(calls) <= len(responses)
                          else dict(approved=True, issues=[], unresolved_questions=[]))
    result, _ = review_behavior(conn, config, profile(behavior_context_chars=budget), 'operation', payload, model)
    assert conn.execute("SELECT * FROM behavior_snapshots WHERE category IN ('service','route_scenario_test') ORDER BY category,identity").fetchall() == preserved
    return conn, config, result, calls, model


def test_latest_review_fits_and_preserves_service_and_all_fifteen_tests():
    payload = latest()
    original = deepcopy(payload)
    assert len(json.dumps(payload)) > 180000
    conn, config, result, calls, model = execute(payload, 180000)
    assert result.approved and payload == original
    supplied = {file['path']: file for request in calls for file in request['bundle']['files']}
    assert supplied == {file['path']: file for file in payload['bundle']['files']}
    assert len([path for path in supplied if path.startswith('src/test/java/')]) == 15
    for request in calls:
        assert request['closure'] == payload['closure']
        for key, unit in request['accepted_units'].items():
            reference = unit['contract_ref']
            index = int(reference.split('[')[1].split(']')[0])
            assert request['bundle']['operation_contract']['units'][index] == payload['accepted_units'][key]['contract']
            assert unit['public_api'] == payload['accepted_units'][key]['public_api']
    before = len(calls)
    review_behavior(conn, config, profile(behavior_context_chars=180000), 'operation', payload, model)
    assert len(calls) == before


def test_smaller_budget_reviews_every_test_and_reuses_accepted_parts():
    payload = latest()
    conn, config, result, calls, model = execute(payload, 130000)
    assert result.approved and len(calls) > 1
    original_tests = {file['path']: file for file in payload['bundle']['files'] if file['path'].startswith('src/test/java/')}
    supplied = [file for request in calls for file in request['bundle']['files'] if file['path'].startswith('src/test/java/')]
    assert len(supplied) == len(original_tests)
    assert {file['path']: file for file in supplied} == original_tests
    main = [file for file in payload['bundle']['files'] if file['path'].startswith('src/main/java/')]
    for request in calls:
        assert [file for file in request['bundle']['files'] if file['path'].startswith('src/main/java/')] == main
        assert request['closure'] == payload['closure']
        assert request['bundle']['operation_contract'] == payload['bundle']['operation_contract']
    before = len(calls)
    review_behavior(conn, config, profile(behavior_context_chars=130000), 'operation', payload, model)
    assert len(calls) == before


def test_split_review_does_not_hide_rejections_or_unresolved_questions():
    _, _, result, _ , _ = execute(latest(), 130000,
        [dict(approved=False, issues=['Routing defect'], unresolved_questions=['Unknown external behavior'])])
    assert not result.approved
    assert result.issues == ['Routing defect']
    assert result.unresolved_questions == ['Unknown external behavior']


def test_indivisible_evidence_fails_explicitly():
    with pytest.raises(ValueError, match='even without tests'):
        execute(latest(), 60000)


def test_interrupted_review_resumes_without_repeating_accepted_part():
    conn, config = state()
    payload = latest()
    settings = profile(behavior_context_chars=180000)
    seen = []
    def interrupted(instruction, encoded):
        request = json.loads(encoded)
        seen.append(request['review_part'])
        if request['review_part'] == 2:
            raise KeyboardInterrupt('simulated launcher interruption')
        return json.dumps(dict(approved=True, issues=[], unresolved_questions=[]))
    with pytest.raises(KeyboardInterrupt):
        review_behavior(conn, config, settings, 'operation', payload, interrupted)
    resumed = []
    def model(instruction, encoded):
        resumed.append(json.loads(encoded)['review_part'])
        return json.dumps(dict(approved=True, issues=[], unresolved_questions=[]))
    result, _ = review_behavior(conn, config, settings, 'operation', payload, model)
    assert seen == [1, 2] and resumed == [2] and result.approved
