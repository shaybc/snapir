"""Content-addressed, append-only fixture/scenario publication and verified loading."""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from models.test_asset_manifest import TestAssetManifest
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def encoded(value):
    """Canonical UTF8 JSON preserves embedded XML text, nulls and numeric values."""
    return json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('utf-8')


def publish(directory, identity, context, bank, junit, comparisons, *, definition_checks=()):
    """Atomically publish a new complete revision; never overwrite an old revision."""
    # Fixture-only operation demos define no JUnit suite; normal JUnit validation remains mandatory at its own stage.
    documents={'fixtures.json':bank.model_dump(mode='json'),'junit-scenarios.json':junit.model_dump(mode='json') if junit is not None else dict(scenarios=[],unresolved=[]),
               'comparison-scenarios.json':comparisons.model_dump(mode='json'),
               'validation.json':dict(definition_checks=list(definition_checks),execution_status='not_run',
                   unresolved=dict(fixtures=bank.unresolved,junit=[*junit.unresolved,*[m for s in junit.scenarios for m in s.unresolved]] if junit is not None else [],
                       comparison=[*comparisons.unresolved,*[m for s in comparisons.scenarios for m in s.unresolved]]))}
    hashes={name:hashlib.sha256(encoded(value)).hexdigest() for name,value in documents.items()}
    context_hash=digest(context);revision=digest(dict(context=context_hash,files=hashes))
    root=Path(directory)/digest(identity)/revision
    manifest=TestAssetManifest(boundary_identity=identity,revision=revision,context_hash=context_hash,files=hashes)
    if root.exists():
        load(root,digest(manifest.model_dump(mode='json')));return root,manifest
    root.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.assets-',dir=root.parent))
    try:
        for name,value in documents.items():(temporary/name).write_bytes(encoded(value))
        (temporary/'manifest.json').write_bytes(encoded(manifest.model_dump(mode='json')))
        try:os.rename(temporary,root)
        except FileExistsError:load(root,digest(manifest.model_dump(mode='json')))
    finally:
        if temporary.exists():shutil.rmtree(temporary)
    return root,manifest


def load(directory, expected_hash):
    """Verify every immutable document before resolving any fixture or running a test."""
    root=Path(directory).resolve();raw=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    manifest=TestAssetManifest.model_validate(raw)
    if digest(raw)!=expected_hash:raise ValueError('Test asset manifest hash changed')
    required={'fixtures.json','junit-scenarios.json','comparison-scenarios.json'}
    if not required<=set(manifest.files) or set(manifest.files)-required-{'validation.json'}:raise ValueError('Unexpected test asset documents')
    result={}
    for name,expected in manifest.files.items():
        path=root/name
        if path.resolve().parent!=root:raise ValueError('Test asset path escaped its revision')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Test asset document changed: '+name)
        result[name]=json.loads(data)
    return manifest,result
