"""Replay stage-six JSON responses and verify actionable correction without source changes."""

import json
import hashlib
from pathlib import Path

import pytest

from runtime.service_generation.response import parse_service_response, ServiceResponseError
from runtime.managed_conversion_response import _remove_response_fence


def responses():
    return json.loads((Path(__file__).parent / 'fixtures/latest_service_generation_responses.json').read_text())


def test_latest_invalid_structural_escapes_are_cleaned_and_valid_responses_unchanged():
    saved = responses()
    for response in saved[:2]:
        assert parse_service_response(response) == json.loads(_remove_response_fence(response))
    with pytest.raises(json.JSONDecodeError):
        json.loads(_remove_response_fence(saved[2]))
    result = parse_service_response(saved[2])
    assert result['files'] and result['dependencies']
    assert 'public class TransferFundsController' in next(content for path, content in result['files'].items() if path.endswith('TransferFundsController.java'))
    assert parse_service_response(json.dumps(result)) == result


def test_unrepairable_json_preserves_response_and_exact_location_for_correction():
    response = json.dumps(parse_service_response(responses()[2]), indent=2).replace('"files":', 'files:', 1)
    with pytest.raises(ServiceResponseError) as caught:
        parse_service_response(response)
    error = caught.value
    assert error.response == response
    assert error.feedback['category'] == 'json_parse'
    assert error.feedback['message'] == 'Expecting property name enclosed in double quotes'
    assert error.feedback['line'] > 0 and error.feedback['column'] > 0
    assert response[error.feedback['offset']:].startswith('files:')
    assert 'complete' in error.feedback['correction'] and 'Preserve approved sources' in error.feedback['correction']


def test_latest_request_has_room_for_precise_json_feedback_without_duplicate_response():
    from copy import deepcopy
    from runtime.service_generation.response import attach_response_correction, RESPONSE_INSTRUCTION
    from runtime.service_generation.operation_wiring import WIRING_INSTRUCTION
    from runtime.behavior_conversion.request_context import encode_request
    payload = json.loads((Path(__file__).parent / 'fixtures/latest_service_generation_request.json').read_text())
    original_sources = deepcopy(payload['approved_sources'])
    malformed = json.dumps(parse_service_response(responses()[2]), indent=2).replace('"files":', 'files:', 1)
    with pytest.raises(ServiceResponseError) as caught:
        parse_service_response(malformed)
    cached = dict(error=str(caught.value), generation_output=None,
        response_correction=caught.value.feedback, previous_generation_response=malformed)
    original = deepcopy(cached)
    payload['validation_feedback'] = cached
    attach_response_correction(payload, cached)
    request, encoded = encode_request(payload, RESPONSE_INSTRUCTION + WIRING_INSTRUCTION + 'x' * 2500, 180000)
    assert len(encoded) + len(RESPONSE_INSTRUCTION + WIRING_INSTRUCTION + 'x' * 2500) <= 180000
    assert request['previous_generation_response'] == malformed
    assert request['approved_sources'] == original_sources
    assert 'previous_generation_response' not in request['validation_feedback']
    assert cached == original


def test_stage_six_correction_reaches_next_request_and_preserves_approved_code_and_tests(tmp_path, monkeypatch):
    from runtime.service_generation import runner
    from tests.runtime.test_service_generation import ready, Verifier
    from tools.maven_dependency_tools.build_context import ManagedBuildContext
    from tools.state_store_tools.behavior_units import initialize, save
    setup = ready(tmp_path)
    conn, config, settings, plan, _ = setup
    item = runner.collect_operation_evidence(conn, config, settings, plan)[0]
    item['payload']['contract'] = {}
    settings.conversion_strategy = 'behavior_units'
    settings.model_provider = 'gemini'
    monkeypatch.setattr(runner, 'collect_operation_evidence', lambda *args: [item])
    from runtime.service_generation.response import RESPONSE_VERSION
    from runtime.workspace_paths import run_report_path
    old_settings = runner.generation_settings_identity(settings).removesuffix(RESPONSE_VERSION)
    old_identity = hashlib.sha256((item['fingerprint'] + run_report_path(tmp_path, 'gate_3_report.txt').read_text() + old_settings).encode()).hexdigest()
    conn.execute('CREATE TABLE service_generation_checkpoints (run_id TEXT, operation_id TEXT, channel TEXT, input_hash TEXT, project_hash TEXT, attempts INTEGER NOT NULL, validation_json TEXT, PRIMARY KEY(run_id,operation_id,channel))')
    conn.execute('INSERT INTO service_generation_checkpoints VALUES (?,?,?,?,?,?,?)',
        (config.run_id, item['operation_id'], item['channel'], old_identity, '', config.max_agent_task_retries, json.dumps({'error': 'Previous validation failure'})))
    conn.commit()
    initialize(conn)
    original = Path(item['project'])
    for number in range(15):
        path = original / f'src/test/java/example/Scenario{number}.java'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'class Scenario{number} {{}}')
        save(conn, config.run_id, 'route_scenario_test', str(number), 'accepted', {'path': str(path)})
    save(conn, config.run_id, 'service', 'accepted-service', 'accepted', {'project': str(original)})
    files = {str(path): path.read_bytes() for path in (original / 'src').rglob('*.java')}
    snapshots = conn.execute('SELECT * FROM behavior_snapshots ORDER BY category,identity').fetchall()
    valid = dict(dependencies=[], files={
        'src/main/java/example/Application.java': '@SpringBootApplication class Application {}',
        'src/main/java/example/Controller.java': '@RestController class Controller { String type = "application/xml"; }',
        'src/test/java/example/WiringTest.java': 'class WiringTest {}',
        'src/main/resources/application.properties': 'server.port=8080'})
    malformed = json.dumps(valid).replace('"files":', 'files:', 1)
    requests = []
    def execute(self, instruction, encoded):
        requests.append(json.loads(encoded))
        assert 'Validate the entire response' in instruction
        return malformed if len(requests) == 1 else json.dumps(valid)
    monkeypatch.setattr(runner.AdkExecutor, 'execute', execute)
    monkeypatch.setattr('runtime.runtime_validation.executor.RuntimeTestExecutor.execute', lambda *args: {})
    validator = lambda *args: dict(build_passed=True, package_passed=True, ibm_guard_passed=True, test_status='passed')
    runner.run_service_generation(conn, config, settings, plan, tmp_path,
        gate_checker=lambda: 'service_generation_pending', validator=validator,
        context_factory=lambda profile, project, artifact: ManagedBuildContext(str(project / 'pom.xml'), Verifier()))
    assert len(requests) == 2
    assert conn.execute('SELECT attempts FROM service_generation_checkpoints').fetchone()[0] == 2
    assert requests[1]['previous_generation_response'] == malformed
    assert requests[1]['response_correction']['category'] == 'json_parse'
    assert requests[1]['response_correction']['offset'] == malformed.index('files:')
    assert conn.execute('SELECT * FROM behavior_snapshots ORDER BY category,identity').fetchall() == snapshots
    assert all(Path(path).read_bytes() == content for path, content in files.items())
