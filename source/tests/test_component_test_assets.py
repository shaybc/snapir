"""Component-to-unit promotion retains verified fixture data and executable scenario links."""
import json
from pathlib import Path
import pytest
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from runtime.test_assets.store import publish,load
from runtime.test_assets.junit_support import stage
from runtime.test_assets.component_assets import restore_component_assets
from runtime.test_assets.preparation import asset_scope,current
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def saved_assets(tmp_path):
    bank=SharedFixtureBank(fixtures={'value':dict(value='source-backed-input')})
    suite=JunitScenarioSuite(scenarios=[dict(scenario_id='echo',purpose='Retain the same input',
        native_entry=dict(owner_type='nativecode.Sample',method_name='echo'),assertions=['Returns the supplied input'])])
    root,manifest=publish(tmp_path/'bank','component',{},bank,suite,ComparisonScenarioSuite())
    identity=digest(manifest.model_dump(mode='json'));component=tmp_path/'component'
    assets=dict(root=str(root),manifest_hash=identity);relative=stage(component,assets)
    report=dict(test_assets=dict(manifest_hash=identity,resource_path=relative,scenario_methods={'echo':'nativecode.SampleTest#echo'}))
    files={'src/test/java/nativecode/SampleTest.java':'package nativecode;public class SampleTest {}'}
    return component,report,files


def test_component_fixture_manifest_is_staged_into_the_complete_unit(tmp_path):
    component,report,files=saved_assets(tmp_path)
    assets=restore_component_assets(component,report,files)
    assert current() is None
    with asset_scope(assets):
        assert current()['tests'].scenario_methods=={'echo':'nativecode.SampleTest#echo'}
        relative=stage(tmp_path/'complete-unit',current())
    assert current() is None
    _,documents=load(tmp_path/'complete-unit'/relative,report['test_assets']['manifest_hash'])
    assert documents['fixtures.json']['fixtures']['value']['value']=='source-backed-input'
    assert documents['junit-scenarios.json']['scenarios'][0]['scenario_id']=='echo'


def test_changed_component_fixture_data_is_rejected(tmp_path):
    component,report,files=saved_assets(tmp_path)
    path=component/report['test_assets']['resource_path']/'fixtures.json'
    path.write_text('{}')
    with pytest.raises(ValueError,match='document changed'):restore_component_assets(component,report,files)


def test_component_fixture_paths_and_scenario_links_cannot_be_substituted(tmp_path):
    component,report,files=saved_assets(tmp_path)
    changed=json.loads(json.dumps(report));changed['test_assets']['resource_path']='../other'
    with pytest.raises(ValueError,match='unexpected resource path'):restore_component_assets(component,changed,files)
    report['test_assets']['scenario_methods']={'another':'nativecode.SampleTest#echo'}
    with pytest.raises(ValueError,match='every declared scenario'):restore_component_assets(component,report,files)


def test_components_without_shared_assets_keep_the_existing_path(tmp_path):
    assert restore_component_assets(tmp_path,{}, {}) is None
