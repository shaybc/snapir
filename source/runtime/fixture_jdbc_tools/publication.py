"""Publish a tested tool distribution atomically; installed versions are never overwritten."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from models.fixture_jdbc_tool_release import FixtureJdbcToolRelease
from runtime.fixture_jdbc_tools.releases import canonical, digest, file_hash, verify_directory
from runtime.fixture_jdbc_tools.artifact_checks import check_packaging


def publish_release(prepared, version, source_fingerprint, store):
    """Install a prepared tested bundle and return its pinned identity and manifest hash."""
    prepared, store = Path(prepared).resolve(), Path(store).resolve()
    check_packaging(prepared / 'jdbc/fixture-jdbc-driver.jar', prepared / 'server/fixture-server.jar')
    evidence = json.loads((prepared / 'evidence/build-receipt.json').read_text(encoding='utf-8'))
    capabilities = json.loads((prepared / 'evidence/capabilities.json').read_text(encoding='utf-8'))
    if (evidence.get('build_passed') is not True or evidence.get('source_fingerprint') != source_fingerprint
            or not evidence.get('java_tests') or not evidence.get('python_tests_passed')
            or evidence.get('python_tests_sha256') != file_hash(prepared / 'evidence/python-tests.xml')
            or evidence.get('driver_sha256') != file_hash(prepared / 'jdbc/fixture-jdbc-driver.jar')
            or evidence.get('server_sha256') != file_hash(prepared / 'server/fixture-server.jar')
            or capabilities.get('protocol') != 1 or capabilities.get('minimum_java') != 21
            or capabilities.get('tool_version') != version):
        raise ValueError('Fixture release requires matching build, test and capability evidence')
    files = {}
    for path in sorted(prepared.rglob('*')):
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(prepared):
            raise ValueError('Prepared release file escaped its directory')
        name = path.relative_to(prepared).as_posix()
        role = 'driver' if name == 'jdbc/fixture-jdbc-driver.jar' else 'server' if name == 'server/fixture-server.jar' else 'wrapper' if name.startswith('bin/') else 'evidence'
        files[name] = dict(sha256=file_hash(path), size=path.stat().st_size, role=role)
    data = FixtureJdbcToolRelease(tool_version=version, bundle_id='0' * 64,
        source_fingerprint=source_fingerprint, fixture_schemas=['test-assets-v1', 'shared-fixtures-v1', 'fixture-jdbc-catalogue-v1'], files=files).model_dump(mode='json')
    descriptor = dict(data)
    descriptor.pop('bundle_id')
    data['bundle_id'] = digest(descriptor)
    bundle_id = data['bundle_id']
    parent = store / 'releases' / version
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / bundle_id
    if target.exists():
        verify_directory(target, bundle_id, digest(data))
    else:
        temporary = Path(tempfile.mkdtemp(prefix='.fixture-release-', dir=parent))
        try:
            shutil.copytree(prepared, temporary, dirs_exist_ok=True)
            (temporary / 'release.json').write_bytes(canonical(data))
            verify_directory(temporary, bundle_id, digest(data))
            try:
                os.rename(temporary, target)
            except OSError:
                if not target.exists():
                    raise
                verify_directory(target, bundle_id, digest(data))
        finally:
            if temporary.exists():
                if temporary.resolve().parent != parent.resolve() or not temporary.name.startswith('.fixture-release-'):
                    raise ValueError('Temporary release cleanup escaped its directory')
                shutil.rmtree(temporary)
    receipts = store / 'installations'
    receipts.mkdir(parents=True, exist_ok=True)
    receipt = canonical(dict(bundle_id=bundle_id, tool_version=version, manifest_hash=digest(data)))
    receipt_path = receipts / (bundle_id + '.json')
    handle, temporary_receipt = tempfile.mkstemp(prefix='.installation-', dir=receipts)
    temporary_receipt = Path(temporary_receipt)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(receipt)
        try:
            os.link(temporary_receipt, receipt_path)
        except FileExistsError:
            if receipt_path.read_bytes() != receipt:
                raise ValueError('Installed tool receipt changed')
    finally:
        temporary_receipt.unlink()
    return dict(bundle_id=bundle_id, tool_version=version, manifest_hash=digest(data), root=str(target))
