"""Reuse content-verified syntax evidence and publish completed workspace revisions."""

import hashlib
import json
from pathlib import Path
import sqlite3
import shutil
from xml.etree import ElementTree


def content_hash(path):
    """Hash source bytes with bounded buffering."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class WorkspaceAnalysis:
    """Cache only complete file-parser results; resolution always uses the current index."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('CREATE TABLE IF NOT EXISTS syntax (path TEXT, hash TEXT, version TEXT, xml TEXT, PRIMARY KEY(path,hash,version))')
        self.conn.execute('CREATE TABLE IF NOT EXISTS revisions (revision TEXT PRIMARY KEY, record_json TEXT)')
        source = Path(__file__).parents[1] / 'java_analysis_tools/source_dependencies'
        self.version = hashlib.sha256(b''.join((source / name).read_bytes() for name in
            ('SourceReferenceScanner.java', 'parser.py', 'resolution.py'))).hexdigest()
        from runtime.java_toolchain import java_version, java_environment
        environment = java_environment()
        executable = shutil.which('java', path=environment.get('PATH') if environment else None)
        release = Path(executable).resolve().parent.parent / 'release' if executable else None
        self.version = hashlib.sha256((self.version + java_version() + str(executable)
            + (content_hash(release) if release and release.is_file() else '')).encode()).hexdigest()
        self.hits = self.misses = 0
        self.observed = {}

    def observe_workspace(self, workspace):
        """Capture the input file set before analysis so later changes cannot publish mixed evidence."""
        for path in sorted(Path(workspace).resolve().rglob('*')):
            if self._input(path):
                self.observed[str(path)] = content_hash(path)

    @staticmethod
    def _input(path):
        return path.is_file() and (path.suffix.lower() in {'.java', '.xml'} or path.name.lower() in {'dse.ini', '.classpath', '.project'})

    def read(self, path, digest, strip_bom):
        """Return cached source syntax only for identical bytes and parser policy."""
        if str(path) in self.observed and self.observed[str(path)] != digest:
            raise ValueError('Source changed during workspace analysis: ' + str(path))
        self.observed[str(path)] = digest
        row = self.conn.execute('SELECT xml FROM syntax WHERE path=? AND hash=? AND version=?',
            (str(path), digest, self.version + str(strip_bom))).fetchone()
        if row:
            try:
                document = ElementTree.fromstring(row[0])
                if document.tag != 'source' or str(Path(document.get('path')).resolve()) != str(Path(path).resolve()):
                    raise ValueError('Invalid cached source identity')
                self.hits += 1
                return document
            except (ElementTree.ParseError, ValueError, TypeError):
                self.conn.execute('DELETE FROM syntax WHERE path=? AND hash=? AND version=?',
                    (str(path), digest, self.version + str(strip_bom)))
        self.misses += 1

    def store(self, path, digest, strip_bom, document):
        """Publish one complete, unchanged source result atomically."""
        self.store_batch({str(path): document}, {str(path): digest}, strip_bom)

    def store_batch(self, documents, hashes, strip_bom):
        """Publish a bounded compiler batch with one transaction, never a partial batch."""
        for path in documents:
            if content_hash(path) != hashes[path]:
                raise ValueError('Java source changed during dependency analysis: ' + str(path))
        with self.conn:
            for path, document in documents.items():
                self.conn.execute('INSERT OR REPLACE INTO syntax VALUES (?,?,?,?)',
                    (str(path), hashes[path], self.version + str(strip_bom), ElementTree.tostring(document, encoding='unicode')))

    def publish(self, workspace, index):
        """Bind a completed revision to current source, XML, and visibility metadata hashes."""
        workspace = Path(workspace).resolve()
        digest = hashlib.sha256(self.version.encode())
        digest.update(index.model_dump_json().encode())
        seen = set()
        for path in sorted(workspace.rglob('*')):
            if self._input(path):
                seen.add(str(path))
                if str(path) not in self.observed:
                    raise ValueError('New source appeared during workspace analysis: ' + str(path))
                digest.update(str(path.relative_to(workspace)).encode())
                current = content_hash(path)
                if str(path) in self.observed and current != self.observed[str(path)]:
                    raise ValueError('Source changed before workspace revision publication: ' + str(path))
                digest.update(current.encode())
        if seen != set(self.observed):
            raise ValueError('Source inputs were removed during workspace analysis')
        revision = digest.hexdigest()
        with self.conn:
            self.conn.execute('INSERT OR REPLACE INTO revisions VALUES (?,?)',
                (revision, json.dumps(dict(workspace=str(workspace), parser_version=self.version))))
        return revision

    def close(self):
        """Close the persistent cache; incomplete workspace revisions are never published."""
        self.conn.close()
