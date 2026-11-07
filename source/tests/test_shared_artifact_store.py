"""Exercise durable publication, integrity checks and index recovery with real files."""
import json
from pathlib import Path
import sqlite3

import pytest

from tools.shared_artifact_store.storage import ArtifactStore
from tools.shared_artifact_store.manifests import contained_path
from tools.shared_artifact_store.locking import artifact_lock


def test_artifact_survives_run_and_index_deletion(tmp_path):
    root = tmp_path / 'shared'
    source = tmp_path / 'run.java'
    source.write_bytes(b'class Example {}')
    with ArtifactStore(root, 'components') as store:
        directory, manifest = store.publish('component-key', {'source/Example.java': source}, {'validated': True})
    source.unlink()
    (root / 'components/registry.db').unlink()
    with ArtifactStore(root, 'components') as store:
        restored = store.find('component-key', revision=manifest['revision'])
        assert restored[1] == manifest
        assert (restored[0] / 'source/Example.java').read_bytes() == b'class Example {}'


def test_corrupt_or_missing_bytes_are_never_reused(tmp_path):
    with ArtifactStore(tmp_path, 'components') as store:
        directory, manifest = store.publish('key', {'source.java': b'good'}, {'validated': True})
        (directory / 'source.java').write_bytes(b'changed')
        assert store.find('key') is None
        assert store.conn.execute('SELECT available FROM artifacts').fetchone()[0] == 0
        (directory / 'source.java').unlink()
        assert store.find('key', revision=manifest['revision']) is None


def test_incomplete_publication_is_not_approved_on_recovery(tmp_path):
    incomplete = tmp_path / 'components/artifacts/key/revision'
    incomplete.mkdir(parents=True)
    (incomplete / 'manifest.json').write_text('{"status":"approved"}')
    with ArtifactStore(tmp_path, 'components') as store:
        assert store.find('key') is None
        assert store.recover_index() == []


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/absolute', 'a\\b'])
def test_storage_rejects_unsafe_paths(tmp_path, name):
    with pytest.raises(ValueError):
        contained_path(tmp_path, name)


def test_publications_are_immutable_and_exact_pins_do_not_float(tmp_path):
    with ArtifactStore(tmp_path, 'components') as store:
        first, a = store.publish('key', {'source': b'first'}, {'validated': True})
        second, b = store.publish('key', {'source': b'second'}, {'validated': True})
        assert a['revision'] != b['revision']
        assert store.find('key', revision=a['revision'])[0] == first
        (first / 'source').unlink()
        assert store.find('key', revision=a['revision']) is None
        assert store.find('key')[0] == second


def test_lock_releases_after_failure(tmp_path):
    with pytest.raises(RuntimeError):
        with artifact_lock(tmp_path, 'component'):
            raise RuntimeError('interrupted')
    with artifact_lock(tmp_path, 'component', timeout=0.1):
        pass


def test_missing_binary_allows_verified_source_rebuilding_only(tmp_path):
    with ArtifactStore(tmp_path, 'components') as store:
        directory, manifest = store.publish('key', {'bundle.json': b'{}', 'artifact.jar': b'compiled'},
                                            {'validated': True, 'jar': 'artifact.jar'})
        (directory / 'artifact.jar').unlink()
        assert store.find('key') is None
        assert store.find_rebuildable('key')[1] == manifest
        (directory / 'bundle.json').write_bytes(b'{"changed":true}')
        assert store.find_rebuildable('key') is None


def test_concurrent_publishers_commit_one_complete_revision(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    def publish(number):
        with ArtifactStore(tmp_path, 'components') as store:
            return store.publish('same-key', {'source': b'same-approved-code'}, {'validated': True})[1]['revision']
    with ThreadPoolExecutor(max_workers=3) as executor:
        revisions = list(executor.map(publish, range(3)))
    assert len(set(revisions)) == 1
    with ArtifactStore(tmp_path, 'components') as store:
        assert store.find('same-key')[1]['revision'] == revisions[0]
        assert store.conn.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 1
