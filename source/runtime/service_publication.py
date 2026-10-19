"""Prepare complete service publication from the existing finalization evidence."""

import hashlib
import json
from pathlib import Path
from models.converted_service_contract import ConvertedServiceContract
from runtime.human_gates import evaluate_gate
from runtime.workspace_paths import run_report_path
from tools.converted_service_registry_tools.location import resolve_registry_settings
from tools.state_store_tools.operation_calls import get_contract


def prepare_publication(conn, config, profile, key, directory):
    """Require finished workflow, packaging/tests/reviews and Gate 4 before registration."""
    channel, operation = key.split('/', 1)
    row = conn.execute('SELECT current_phase FROM runs WHERE run_id=?', (config.run_id,)).fetchone()
    if row is None or row[0] != 'operation_workflow_completed':
        raise ValueError('Operation workflow has not completed')
    manifest = json.loads(run_report_path(directory, 'delivery_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('production_ready') is not True or manifest.get('blockers') or len(manifest['operations']) != 1:
        raise ValueError('Complete validated operation delivery evidence is required')
    item = manifest['operations'][0]
    if (item['channel'], item['operation_id']) != (channel, operation) or item.get('blockers'):
        raise ValueError('Delivery evidence belongs to another or incomplete operation')
    if not item.get('files') or not any(name.endswith('.jar') for name in item['files']):
        raise ValueError('Packaged service artifact is required for publication')
    for relative, digest in item['files'].items():
        path = (Path(directory) / relative).resolve()
        if not path.is_relative_to(Path(directory).resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Validated delivery artifact is missing or changed')
    validation_row = conn.execute('SELECT validation_json FROM service_generation_checkpoints WHERE run_id=? AND operation_id=? AND channel=?',
                                  (config.run_id, operation, channel)).fetchone()
    if validation_row is None:
        raise ValueError('Service packaging validation is missing')
    validation = json.loads(validation_row[0])
    if any(validation.get(name) is not True for name in ('build_passed', 'package_passed', 'ibm_guard_passed')) or any(
        validation.get(name) != 'passed' for name in ('test_status', 'xml_compatibility', 'behavioral_equivalence', 'legacy_trace_comparison')):
        raise ValueError('Service packaging and operation tests must pass before publication')
    report4 = run_report_path(directory, 'gate_4_report.txt').read_text(encoding='utf-8')
    from runtime.gate_one_reports import read_gate_one_reports
    for number in (1, 2, 3):
        report = read_gate_one_reports(directory) if number == 1 else run_report_path(directory, f'gate_{number}_report.txt').read_text(encoding='utf-8')
        if evaluate_gate(conn, config.run_id, number, report, 'human', True) != 'approved':
            raise ValueError('Every operation gate must be approved before publication')
    if evaluate_gate(conn, config.run_id, 4, report4, 'human', True) != 'approved':
        raise ValueError('Operation Gate 4 approval is required')
    native = get_contract(conn, config.run_id, key)
    formats = native['formats']
    if any(role not in formats or formats[role].get('unresolved') for role in ('csRequestFormat','csReplyFormat','csErrorReplyFormat')):
        raise ValueError('Complete request, reply and error API definitions are required')
    application_id, _ = resolve_registry_settings(profile)
    definition = dict(format='native-xml-http', method=native['method'], path=native['path'],
                      media_type=native['media_type'], formats=formats, error_policy=native['error_policy'],
                      artifact_evidence=dict(root=str(Path(directory).resolve()), files=item['files']))
    revision = hashlib.sha256(json.dumps(dict(api=definition, files=item['files']), sort_keys=True).encode()).hexdigest()
    values = profile.deployment_values.get(key, {})
    address = dict(base_url_property=native['base_url_property'],
                   port=values.get('container_port', profile.deployment_defaults.container_port))
    if values.get('base_url'):
        address['base_url'] = values['base_url']
    return ConvertedServiceContract(application_id=application_id, channel=channel, operation_id=operation,
        api_revision=revision, service_id=key, artifact_reference=str(Path(directory) / 'services' / channel / operation),
        method=native['method'], path=native['path'], media_types=[native['media_type']],
        request_contract=formats['csRequestFormat'], response_contract=formats['csReplyFormat'],
        error_contract=formats['csErrorReplyFormat'], api_definition=definition,
        addresses={profile.deployment_environment: address}, completion=dict(source_run_id=config.run_id,
            validation_report_reference=str(run_report_path(directory, 'final_report.md')), conversion_passed=True,
            package_passed=True, tests_passed=True, review_approved=True, gates_approved=True)).model_dump(mode='json')


def verify_publication_artifacts(publication):
    """Retain package integrity when recovering an interrupted prepared publication."""
    evidence = publication['api_definition']['artifact_evidence']
    root = Path(evidence['root']).resolve()
    for relative, digest in evidence['files'].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Prepared publication artifacts changed; restore the validated operation artifacts')
