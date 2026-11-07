"""Publish immutable artifacts before exposing them through a recoverable SQLite index."""
import json
import logging
from pathlib import Path
import shutil
import sqlite3
import tempfile

from tools.shared_artifact_store.manifests import content_hash, file_hash, contained_path, read_manifest


class ArtifactStore:
    """Store approved component or operation versions independently of run history."""

    def __init__(self, root, kind):
        """Open an index, rebuilding a missing index only from complete verified artifacts."""
        if kind not in {'components', 'operations'}:
            raise ValueError('Unknown shared artifact kind')
        self.root = Path(root).resolve()
        self.kind = kind
        self.directory = self.root / kind
        self.directory.mkdir(parents=True, exist_ok=True)
        marker = self.root / 'store.json'
        from tools.shared_artifact_store.locking import artifact_lock
        with artifact_lock(self.root, 'store-initialization'):
            try:
                with marker.open('x', encoding='utf-8') as stream:
                    json.dump({'schema_version': 1}, stream)
            except FileExistsError:
                if json.loads(marker.read_text(encoding='utf-8')).get('schema_version') != 1:
                    raise ValueError('Unsupported shared store schema')
        database = self.directory / 'registry.db'
        with artifact_lock(self.root, ['index-initialization', kind]):
            missing = not database.exists()
            self.conn = sqlite3.connect(database, timeout=30)
            self.conn.execute('PRAGMA journal_mode=WAL')
            index_missing = not self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='artifacts'").fetchone()
            self.conn.execute('CREATE TABLE IF NOT EXISTS artifacts (lookup_key TEXT NOT NULL, revision TEXT PRIMARY KEY, path TEXT NOT NULL, available INTEGER NOT NULL DEFAULT 1)')
            self.conn.commit()
        if missing or index_missing:
            self.recover_index()

    def close(self):
        """Release the SQLite connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.close()

    def _index(self, path, manifest):
        relative = path.relative_to(self.directory).as_posix()
        with self.conn:
            self.conn.execute('INSERT OR REPLACE INTO artifacts VALUES (?,?,?,1)',
                              (manifest['lookup_key'], manifest['revision'], relative))

    def recover_index(self):
        """Recover indexes after deletion or interrupted publication; never approve partial output."""
        recovered = []
        for path in (self.directory / 'artifacts').glob('*/*/manifest.json'):
            try:
                data = read_manifest(path.parent)
                if data['kind'] != self.kind:
                    raise ValueError('Artifact belongs to another registry')
                self._index(path.parent, data)
                recovered.append(data['revision'])
            except (OSError, ValueError, KeyError) as error:
                logging.getLogger(__name__).warning('Shared artifact recovery skipped %s: %s', path.parent, error)
        return recovered

    def find(self, lookup_key, *, revision=None):
        """Return a verified artifact or a miss; a pinned missing revision never selects another."""
        rows = self.conn.execute('SELECT revision,path FROM artifacts WHERE lookup_key=?' +
                                 (' AND revision=?' if revision else '') + ' ORDER BY rowid DESC',
                                 (lookup_key, revision) if revision else (lookup_key,)).fetchall()
        if not rows:
            # A crash after the directory rename but before the index commit leaves a complete publication.
            for path in (self.directory / 'artifacts' / content_hash(lookup_key)).glob('*/manifest.json'):
                try:
                    data = read_manifest(path.parent)
                    if data['lookup_key'] == lookup_key and (revision is None or data['revision'] == revision):
                        self._index(path.parent, data)
                        return path.parent, data
                except (OSError, ValueError, KeyError):
                    continue
        for saved_revision, relative in rows:
            path = contained_path(self.directory, relative)
            try:
                manifest = read_manifest(path)
                if manifest['lookup_key'] != lookup_key or manifest['revision'] != saved_revision:
                    raise ValueError('Artifact index disagrees with its manifest')
                return path, manifest
            except (OSError, ValueError, KeyError) as error:
                logging.getLogger(__name__).warning('Shared artifact unavailable: %s: %s', saved_revision, error)
                with self.conn:
                    self.conn.execute('UPDATE artifacts SET available=0 WHERE revision=?', (saved_revision,))
        return None

    def find_rebuildable(self, lookup_key):
        """Permit source rebuilding only when every non-JAR byte still matches its approved manifest."""
        rows = self.conn.execute('SELECT path FROM artifacts WHERE lookup_key=? ORDER BY rowid DESC', (lookup_key,)).fetchall()
        if not rows:
            rows = [(path.parent.relative_to(self.directory).as_posix(),) for path in
                    (self.directory / 'artifacts' / content_hash(lookup_key)).glob('*/manifest.json')]
        for relative, in rows:
            path = contained_path(self.directory, relative)
            try:
                manifest = read_manifest(path, verify=False)
                jar = manifest['metadata']['jar']
                if manifest['lookup_key'] != lookup_key or 'bundle.json' not in manifest['files']:
                    continue
                for name, expected in manifest['files'].items():
                    if name != jar and file_hash(contained_path(path, name)) != expected:
                        raise ValueError('Shared source evidence changed')
                return path, manifest
            except (OSError, ValueError, KeyError):
                continue
        return None

    def publish(self, lookup_key, files, metadata):
        """Publish validated bytes atomically; callers must supply completion evidence in metadata."""
        if not files or metadata.get('validated') is not True:
            raise ValueError('Shared publication requires validated artifacts')
        staging = self.directory / '.staging'
        staging.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=staging) as temporary:
            staged = Path(temporary) / 'artifact'
            staged.mkdir()
            for name, source in files.items():
                if name == 'manifest.json':
                    raise ValueError('Artifact files cannot replace their publication manifest')
                destination = contained_path(staged, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(source, bytes):
                    destination.write_bytes(source)
                else:
                    source = Path(source)
                    if source.is_symlink():
                        raise ValueError('Cannot publish linked artifacts')
                    shutil.copyfile(source, destination)
            manifest = dict(schema_version=1, kind=self.kind, status='approved', lookup_key=lookup_key,
                            metadata=metadata, files={name: file_hash(staged / name) for name in sorted(files)})
            manifest['revision'] = content_hash(manifest)
            (staged / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8')
            destination = self.directory / 'artifacts' / content_hash(lookup_key) / manifest['revision']
            from tools.shared_artifact_store.locking import artifact_lock
            with artifact_lock(self.root, ['publication', self.kind, lookup_key]):
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    previous = read_manifest(destination, verify=False)
                    if previous != manifest:
                        raise ValueError('Immutable shared revision contains conflicting metadata')
                    for name, expected in manifest['files'].items():
                        target = contained_path(destination, name)
                        if not target.exists() or file_hash(target) != expected:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(staged / name, target)
                    read_manifest(destination)
                else:
                    staged.rename(destination)
                self._index(destination, manifest)
            return destination, manifest
