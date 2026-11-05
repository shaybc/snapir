"""Bind optional demo approvals to exact tool and fixture revision evidence."""
import json
from pathlib import Path
from models.fixture_demo_catalogue import FixtureDemoCatalogue
from runtime.fixture_jdbc_tools.releases import digest,file_hash,verify_directory
from runtime.test_assets.store import load
from runtime.fixture_demo.artifact_paths import demo_artifact


def demo_evidence(directory,infrastructure):
    """Reverify every referenced immutable revision; never accept a report's success flag alone."""
    directory=Path(directory)
    verify_directory(directory/infrastructure.toolRoot,infrastructure.bundleId,infrastructure.manifestHash)
    path=directory/infrastructure.catalogue
    raw=json.loads(path.read_text(encoding='utf-8'))
    if digest(raw)!=infrastructure.catalogueHash:raise ValueError('Demo catalogue changed after preparation')
    catalogue=FixtureDemoCatalogue.model_validate(raw);assets={}
    for scenario in catalogue.scenarios.values():
        for resource in scenario.resources.values():
            for reference in resource.fixtures:
                root=(path.parent/reference.asset_root).resolve()
                load(root,reference.manifest_hash)
                assets[str(root)]=reference.manifest_hash
    return dict(catalogue_hash=infrastructure.catalogueHash,tool_bundle=infrastructure.bundleId,
        tool_manifest=infrastructure.manifestHash,fixture_revisions=assets,
        definition_hash=file_hash(demo_artifact(directory,'operation-demo-scenarios.json')))
