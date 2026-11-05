"""Verify caller-pinned immutable releases without compiling, downloading or reading fixtures."""
import hashlib
import json
import re
from pathlib import Path
from models.fixture_jdbc_tool_release import FixtureJdbcToolRelease


def canonical(value):
    """Use the converter's canonical ASCII JSON representation for release identities."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest(value):
    """Hash metadata independently of JSON indentation or dictionary insertion order."""
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    """Hash exact bytes without newline or encoding normalization."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def default_store():
    """Return the converter-owned distribution location, independent of operation output."""
    return Path(__file__).resolve().parents[2] / 'resources/fixture-jdbc'


def verify_directory(directory, bundle_id, expected_manifest_hash=None):
    """Validate metadata and every file against an externally pinned bundle identity."""
    if not re.fullmatch(r'[a-f0-9]{64}', bundle_id):
        raise ValueError('A pinned fixture tool bundle ID is required')
    root = Path(directory).resolve()
    raw = json.loads((root / 'release.json').read_text(encoding='utf-8'))
    release = FixtureJdbcToolRelease.model_validate(raw)
    if expected_manifest_hash is not None and digest(raw) != expected_manifest_hash:
        raise ValueError('Fixture tool manifest hash changed')
    descriptor = release.model_dump(mode='json')
    descriptor.pop('bundle_id')
    if release.bundle_id != bundle_id or digest(descriptor) != bundle_id:
        raise ValueError('Fixture tool bundle identity changed')
    for name, entry in release.files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Fixture tool file missing or escaped release root: ' + name)
        if path.stat().st_size != entry.size or file_hash(path) != entry.sha256:
            raise ValueError('Fixture tool file changed: ' + name)
    actual = {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()}
    if actual != {'release.json', *release.files}:
        raise ValueError('Fixture tool release has unlisted files')
    return release


def locate_release(bundle_id, store=None):
    """Look up only an explicitly installed bundle; no latest, fallback build, or network."""
    root = Path(store) if store is not None else default_store()
    if not re.fullmatch(r'[a-f0-9]{64}', bundle_id):
        raise ValueError('A pinned fixture tool bundle ID is required')
    receipt = json.loads((root / 'installations' / (bundle_id + '.json')).read_text(encoding='utf-8'))
    version = receipt.get('tool_version', '')
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid installed fixture tool version')
    directory = root / 'releases' / version / bundle_id
    release = verify_directory(directory, bundle_id, receipt['manifest_hash'])
    return directory, release
