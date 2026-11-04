"""Publish an operation request from a successful, retained request-format fixture."""

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from models.shared_test_fixture import SharedFixtureBank
from models.comparison_test_scenario import ComparisonScenarioSuite
from runtime.test_assets.references import resolve
from runtime.test_assets.store import load


def write_sample_request(project, artifact_root, validation_report):
    """Copy a matched non-exception unformat fixture verbatim."""
    root = Path(artifact_root)
    receipt = validation_report.get('test_assets')
    if not receipt:
        raise ValueError('Standalone sample requires request-format test fixtures')
    manifest_hash = receipt['manifest_hash']
    _, documents = load(root / 'src/test/resources/shared-test-assets' / manifest_hash, manifest_hash)
    bank = SharedFixtureBank.model_validate(documents['fixtures.json'])
    scenarios = ComparisonScenarioSuite.model_validate(documents['comparison-scenarios.json'])
    report_path = root / 'format-diagnostic/execution/format-comparison.json'
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    if not report.get('inputs_unchanged') or report.get('fixture_manifest_hash') != manifest_hash:
        raise ValueError('Standalone sample request comparison evidence changed')
    for scenario in scenarios.scenarios:
        if scenario.direction != 'unformat' or scenario.input_xml is None or scenario.unresolved:
            continue
        xml = resolve(bank, scenario.input_xml)
        if not isinstance(xml, str) or not xml.strip():
            continue
        observed = next((item for item in report.get('cases', [])
                         if item['case']['case_id'] == scenario.scenario_id), None)
        native = observed.get('native', {}) if observed else {}
        if not (observed and observed['status'] == 'matched' and
                observed['case'].get('input_xml') == xml and native.get('status') == 'completed' and
                native.get('invocation_completed') and not native.get('exception') and
                not native.get('failure_origin')):
            continue
        ElementTree.fromstring(xml)
        project = Path(project)
        (project / 'standalone/sample-request.xml').write_text(xml, encoding='utf-8')
        return project / 'standalone/sample-request.xml'
    raise ValueError('No successful non-exception request-format XML fixture is available for the standalone sample')


def write_operation_sample(conn, config, project, bindings):
    """Find the current accepted request-format artifact, never another operation's fixtures."""
    from tools.conversion_tools.component_identity import checked_plan, component_group
    from tools.state_store_tools import component_records as records
    from models.native_component_result import NativeComponentResult
    request = bindings.get('csRequestFormat')
    row = conn.execute('SELECT plan_json FROM conversion_component_plans WHERE run_id=?', (config.run_id,)).fetchone()
    if request is None or row is None:
        raise ValueError('Standalone sample requires the assembled operation request-format binding and component plan')
    plan = checked_plan(json.loads(row[0]))
    identity = plan.unit_roots[request['unit_id']]
    group = component_group(plan, identity)
    head = records.head(conn, config.run_id, group.group_id)
    if head is None or head['status'] != 'component_validated':
        raise ValueError('Standalone request-format component is not validated')
    result = records.read_record(conn, config.run_id, group.group_id, 'result', head['result_revision'])
    artifact = NativeComponentResult.model_validate(result['results'][identity])
    report_path = Path(artifact.artifact_root) / artifact.validation_report
    raw = report_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != artifact.validation_report_hash:
        raise ValueError('Standalone request-format validation report changed')
    return write_sample_request(project, artifact.artifact_root, json.loads(raw))
