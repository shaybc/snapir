"""Acceptance for immutable release publication, exact staging, and owned server lifecycle."""
import hashlib
import json
import socket
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile
import pytest
from runtime.fixture_jdbc_tools.publication import publish_release
from runtime.fixture_jdbc_tools.releases import digest, locate_release, verify_directory
from runtime.fixture_jdbc_tools.staging import stage_release
from fixture_jdbc_support import assets, command, ensure, free_port, server_jar, source_root


def prepared(root):
    for name, value in [('bin/fixture-server.bat', b'wrapper'), ('evidence/python-tests.xml', b'<testsuites/>')]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (root / 'jdbc').mkdir()
    (root / 'server').mkdir()
    driver = source_root() / 'jdbc-fixture-java/fixture-driver/target/fixture-jdbc-driver-1.0.0-standalone.jar'
    shutil.copyfile(driver, root / 'jdbc/fixture-jdbc-driver.jar')
    shutil.copyfile(server_jar(), root / 'server/fixture-server.jar')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    receipt = dict(build_passed=True, source_fingerprint='a' * 64, java_tests=[dict(tests=1)], python_tests_passed=1,
        python_tests_sha256=sha(root / 'evidence/python-tests.xml'), driver_sha256=sha(driver), server_sha256=sha(server_jar()))
    (root / 'evidence/build-receipt.json').write_text(json.dumps(receipt))
    (root / 'evidence/capabilities.json').write_text(json.dumps(dict(tool_version='1.0.0', protocol=1, minimum_java=21)))
    return root


def test_publish_stage_and_verify_are_exact_and_do_not_build(tmp_path, monkeypatch):
    source = prepared(tmp_path / 'prepared')
    store = tmp_path / 'converter-store'
    receipt = publish_release(source, '1.0.0', 'a' * 64, store)
    assert publish_release(source, '1.0.0', 'a' * 64, store) == receipt
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: pytest.fail('Lookup/stage attempted external build or execution'))
    destination = tmp_path / 'generated/demo-tools' / receipt['bundle_id']
    result = stage_release(receipt['bundle_id'], destination, store)
    assert result == stage_release(receipt['bundle_id'], destination, store)
    assert result['manifest_hash'] == receipt['manifest_hash']
    assert not (tmp_path / 'generated/lib').exists()
    assert not list(destination.rglob('fixtures.json'))
    verify_directory(destination, receipt['bundle_id'], receipt['manifest_hash'])
    (destination / 'jdbc/fixture-jdbc-driver.jar').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='changed'):
        stage_release(receipt['bundle_id'], destination, store)


@pytest.mark.parametrize('mutation', ['manifest', 'binary', 'extra', 'receipt', 'path'])
def test_release_tampering_and_missing_installations_never_fallback(tmp_path, mutation):
    receipt = publish_release(prepared(tmp_path / 'prepared'), '1.0.0', 'a' * 64, tmp_path / 'store')
    root = Path(receipt['root'])
    if mutation == 'manifest':
        value = json.loads((root / 'release.json').read_text());value['minimum_java'] = 17
        (root / 'release.json').write_text(json.dumps(value))
    elif mutation == 'binary':
        (root / 'server/fixture-server.jar').write_bytes(b'changed')
    elif mutation == 'extra':
        (root / 'unexpected.jar').write_bytes(b'extra')
    elif mutation == 'path':
        value = json.loads((root / 'release.json').read_text());value['files']['../escape'] = next(iter(value['files'].values()))
        (root / 'release.json').write_text(json.dumps(value))
    else:
        (tmp_path / 'store/installations' / (receipt['bundle_id'] + '.json')).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        locate_release(receipt['bundle_id'], tmp_path / 'store')


def test_packaged_driver_is_self_contained_and_has_no_application_shadow_classes():
    driver = source_root() / 'jdbc-fixture-java/fixture-driver/target/fixture-jdbc-driver-1.0.0-standalone.jar'
    with ZipFile(driver) as jar:
        names = jar.namelist()
        assert 'il/co/dcd/fixtures/jdbc/FixtureDriver.class' in names
        assert 'il.co.dcd.fixtures.jdbc.FixtureDriver' in jar.read('META-INF/services/java.sql.Driver').decode()
        assert not any(n.startswith(('com/fasterxml/', 'org/springframework/', 'il/co/dcd/fixtures/server/')) for n in names)
        assert any(n.startswith('il/co/dcd/fixtures/internal/jackson/') for n in names)


def test_ensure_reuses_only_owned_identical_server_and_never_changes_fixtures(tmp_path):
    url, state, args, first = ensure(tmp_path)
    try:
        assert first['reused'] is False and 'owner_token' not in first
        with ThreadPoolExecutor(2) as pool:
            receipts = list(pool.map(lambda _: json.loads(command(*args).stdout), range(2)))
        assert all(r['reused'] and r['server'] == first['server'] for r in receipts)
        status = json.loads(command('status', '--state-dir', state).stdout)
        assert status['server'] == first['server'] and 'owner_token' not in status
        bad = list(args);bad[bad.index('--expected-hash') + 1] = '0' * 64
        assert command(*bad, check=False).returncode != 0
    finally:
        assert command('stop', '--state-dir', state).returncode == 0
    assert command('status', '--state-dir', state, check=False).returncode != 0


def test_busy_port_and_stale_or_forged_ownership_do_not_kill_another_process(tmp_path):
    catalogue, definition, _ = assets(tmp_path)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0));listener.listen(2)
        url = f'jdbc:fixtures://127.0.0.1:{listener.getsockname()[1]}/success'
        result = command('ensure', '--jdbc-url', url, '--catalogue', catalogue, '--expected-hash', digest(definition), '--state-dir', tmp_path / 'busy', check=False)
        assert result.returncode != 0
        assert listener.fileno() != -1
    directory = tmp_path / 'owned'
    directory.mkdir()
    url, state, args, _ = ensure(directory)
    state_path = state / 'server.json'
    original = state_path.read_bytes()
    try:
        forged = json.loads(original);forged['process_start'] = 'not-the-process-start'
        state_path.write_text(json.dumps(forged))
        assert command('stop', '--state-dir', state, check=False).returncode != 0
    finally:
        state_path.write_bytes(original)
        command('stop', '--state-dir', state)


def test_tool_capabilities_are_explicit_and_no_full_jdbc_claim():
    data = json.loads(command('capabilities').stdout)
    assert data['protocol'] == 1 and data['minimum_java'] == 21
    assert 'full_jdbc_compliance' in data['unsupported']


def test_untested_distribution_cannot_be_published(tmp_path):
    tree = prepared(tmp_path / 'prepared')
    (tree / 'evidence/build-receipt.json').write_text('{}')
    with pytest.raises(ValueError, match='requires matching'):
        publish_release(tree, '1.0.0', 'a' * 64, tmp_path / 'store')
    assert not (tmp_path / 'store/releases').exists()


def test_concurrent_first_start_serializes_and_uses_one_owned_process(tmp_path):
    catalogue, definition, _ = assets(tmp_path)
    url = f'jdbc:fixtures://127.0.0.1:{free_port()}/success'
    state = tmp_path / 'runtime'
    args = ('ensure', '--jdbc-url', url, '--catalogue', catalogue, '--expected-hash', digest(definition),
        '--state-dir', state, '--fixture-root', tmp_path)
    try:
        with ThreadPoolExecutor(2) as pool:
            receipts = list(pool.map(lambda _: json.loads(command(*args).stdout), range(2)))
        assert len({r['server'] for r in receipts}) == 1
        assert sorted(r['reused'] for r in receipts) == [False, True]
    finally:
        command('stop', '--state-dir', state, check=False)


def test_concurrent_publication_and_staging_never_replace_a_different_bundle(tmp_path):
    tree = prepared(tmp_path / 'prepared')
    store = tmp_path / 'store'
    with ThreadPoolExecutor(2) as pool:
        receipts = list(pool.map(lambda _: publish_release(tree, '1.0.0', 'a' * 64, store), range(2)))
    assert receipts[0] == receipts[1]
    target = tmp_path / 'staged'
    with ThreadPoolExecutor(2) as pool:
        bindings = list(pool.map(lambda _: stage_release(receipts[0]['bundle_id'], target, store), range(2)))
    assert bindings[0] == bindings[1]
    with pytest.raises(ValueError, match='pinned'):
        locate_release('latest', store)
