"""Samples come from the exact request fixtures that parsed successfully."""

import json
import shutil
from types import SimpleNamespace

import pytest

from models.comparison_test_scenario import ComparisonScenarioSuite
from models.junit_test_scenario import JunitScenarioSuite
from models.shared_test_fixture import SharedFixtureBank
from runtime.behavior_conversion.standalone_sample import write_sample_request, write_operation_sample
from runtime.test_assets.store import publish
from tools.conversion_tools.scoped_reuse.fingerprints import digest


XML = '<Request xmlns="urn:example"><ClientID>A&amp;B</ClientID></Request>'


def assets(tmp_path):
    entry = dict(owner_type='ExampleFormat', method_name='unformat')
    bank = SharedFixtureBank(fixtures={'bad': dict(kind='xml', value='<Request/>'),
                                      'good': dict(kind='xml', value=XML)})
    suite = ComparisonScenarioSuite(scenarios=[dict(scenario_id=name, purpose=name,
        direction='unformat', native_entry=entry, input_xml=dict(fixture_id=name)) for name in ('bad', 'good')])
    junit = JunitScenarioSuite(scenarios=[dict(scenario_id='unit', purpose='parse',
        native_entry=entry, assertions=['assertNotNull(result)'])])
    published, manifest = publish(tmp_path/'published', 'request-format', {}, bank, junit, suite)
    key = digest(manifest.model_dump(mode='json'))
    artifact = tmp_path/'request-artifact'
    shutil.copytree(published, artifact/'src/test/resources/shared-test-assets'/key)
    report = dict(inputs_unchanged=True, fixture_manifest_hash=key, cases=[
        dict(case=dict(case_id=name, input_xml=bank.fixtures[name].value), status='matched',
             native=dict(status='completed', invocation_completed=True, failure_origin=None,
                         exception={'type':'ExpectedFailure'} if name=='bad' else None)) for name in ('bad','good')])
    path = artifact/'format-diagnostic/execution/format-comparison.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(report))
    project = tmp_path/'operation'
    (project/'standalone').mkdir(parents=True)
    return project, artifact, dict(test_assets=dict(manifest_hash=key)), path, report


def test_sample_skips_negative_cases_and_preserves_exact_xml(tmp_path):
    project, artifact, validation, _, _ = assets(tmp_path)
    (project/'Operation.java').write_text('unchanged')
    sample = write_sample_request(project, artifact, validation)
    assert sample == project/'standalone/sample-request.xml'
    assert sample.read_bytes() == XML.encode('utf-8')
    assert not (project/'sample-request.xml').exists()
    assert not (project/'standalone/sample-request.json').exists()
    assert (project/'Operation.java').read_text()=='unchanged'


@pytest.mark.parametrize('change', ['all_exceptions','changed_xml','changed_manifest','incomplete'])
def test_sample_rejects_unproven_or_changed_inputs(tmp_path, change):
    project, artifact, validation, path, report = assets(tmp_path)
    if change=='all_exceptions': report['cases'][1]['native']['exception']={'type':'Failure'}
    if change=='changed_xml': report['cases'][1]['case']['input_xml']='<Other/>'
    if change=='changed_manifest': report['fixture_manifest_hash']='other'
    if change=='incomplete': report['cases'][1]['native']['status']='failed'
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError): write_sample_request(project, artifact, validation)
    assert not (project/'standalone/sample-request.xml').exists()


def test_operation_sample_does_not_search_another_operations_assets(tmp_path):
    class Connection:
        def execute(self, *args): return SimpleNamespace(fetchone=lambda: None)
    with pytest.raises(ValueError, match='request-format binding'):
        write_operation_sample(Connection(), SimpleNamespace(run_id='run'), tmp_path, {})
