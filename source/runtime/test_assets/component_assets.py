"""Restore immutable component test assets for whole-unit validation."""
from pathlib import Path
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from models.native_test_bundle import NativeTestBundle
from runtime.test_assets.store import load
from runtime.test_assets.junit_support import check_definition


def restore_component_assets(artifact_root,report,files):
    """Reuse exact retained fixtures and scenario links, never regenerate test data."""
    receipt=report.get('test_assets')
    if not receipt:return None
    manifest_hash=receipt['manifest_hash']
    if len(manifest_hash)!=64 or any(c not in '0123456789abcdef' for c in manifest_hash):
        raise ValueError('Invalid retained test asset manifest identity')
    relative='src/test/resources/shared-test-assets/'+manifest_hash
    if receipt['resource_path']!=relative:raise ValueError('Retained test assets have an unexpected resource path')
    root=Path(artifact_root).resolve();directory=(root/relative).resolve()
    if not directory.is_relative_to(root):raise ValueError('Retained test assets escaped the component root')
    _,documents=load(directory,manifest_hash)
    assets=dict(root=str(directory),manifest_hash=manifest_hash,
        bank=SharedFixtureBank.model_validate(documents['fixtures.json']),
        junit=JunitScenarioSuite.model_validate(documents['junit-scenarios.json']),
        comparisons=ComparisonScenarioSuite.model_validate(documents['comparison-scenarios.json']))
    tests=NativeTestBundle(files=[dict(path=p,content=t) for p,t in files.items() if p.startswith('src/test/java/')],
        fixture_manifest_hash=manifest_hash,scenario_methods=receipt['scenario_methods'])
    check_definition(tests,assets)
    return dict(assets,tests=tests)
