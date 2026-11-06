"""Read immutable schema-four map facts without loading a workspace manifest or graph."""

from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

MAX_RECORD_BYTES = 4 * 1024 * 1024
_validated = set()


def bounded_json(value):
    """Decode one bounded record, never an array containing a complete project."""
    if len(value.encode('utf-8')) > MAX_RECORD_BYTES:
        raise ValueError('Indexed analysis record exceeds 4 MiB')
    return json.loads(value)


class SqlSequence(Sequence):
    """Hydrate one indexed row at a time, including when callers request iteration."""

    def __init__(self, conn, query, decode, parameters=()):
        self.conn, self.query, self.decode, self.parameters = conn, query, decode, parameters

    def __iter__(self):
        for row in self.conn.execute(self.query, self.parameters):
            yield self.decode(row)

    def __len__(self):
        return self.conn.execute('SELECT count(*) FROM (' + self.query + ')', self.parameters).fetchone()[0]

    def __getitem__(self, index):
        if isinstance(index, slice):
            raise TypeError('Iterate indexed inventory instead of slicing it into a list')
        if index < 0:
            index += len(self)
        row = self.conn.execute(self.query + ' LIMIT 1 OFFSET ?', (*self.parameters, index)).fetchone()
        if row is None:
            raise IndexError(index)
        return self.decode(row)


def digest(path):
    """Hash with bounded buffering."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class IndexedAnalysis(dict):
    """Expose compatible manifest fields as readonly SQL sequences, with an explicit lifetime."""

    def __init__(self, root, *, progress=None, validate_notes=True, receipt=None, trusted_publication=False):
        self.root = Path(root).resolve()
        descriptor = self.root / 'vault-manifest.json'
        if descriptor.stat().st_size > 65536:
            raise ValueError('Indexed map descriptor exceeds 64 KiB')
        metadata = bounded_json(descriptor.read_text(encoding='utf-8-sig'))
        self.manifest_hash=digest(descriptor)
        if metadata.get('vault_schema_version') != 4 or metadata.get('identity_version') != 1 or metadata.get('complete') is not True:
            raise ValueError('Incomplete or unsupported indexed analysis')
        if (self.root / 'vault-generation.json').exists():
            raise ValueError('Indexed map generation is incomplete')
        required = {'java-edges-v1', 'original-consumers-v1', 'context-java-roots-v1', 'indexed-xml'}
        if not required <= set(metadata.get('capabilities', [])):
            raise ValueError('Indexed map lacks required analysis capabilities; regenerate it')
        self.database = self.safe_path(metadata['analysis_store'])
        if digest(self.database) != metadata.get('analysis_hash'):
            raise ValueError('Indexed analysis database changed or is truncated')
        self.conn = sqlite3.connect(self.database.as_uri() + '?mode=ro&immutable=1', uri=True)
        self.conn.execute('PRAGMA cache_size=-8192')
        self.conn.execute('PRAGMA temp_store=FILE')
        self.source_root = Path(self.conn.execute("SELECT value FROM revision WHERE key='source_root'").fetchone()[0])
        if self.conn.execute("SELECT value FROM revision WHERE key='complete'").fetchone() != ('true',):
            raise ValueError('Indexed analysis revision is incomplete')
        if self.conn.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('Indexed analysis database failed integrity checks')
        super().__init__(metadata)
        self['channels'] = [row[0] for row in self.conn.execute("SELECT key FROM sets WHERE collection='channels' ORDER BY key")]
        self['entities'] = SqlSequence(self.conn, 'SELECT data,note_hash FROM notes WHERE definition IS NOT NULL ORDER BY path', self._entry)
        self['operation_contexts'] = SqlSequence(self.conn, 'SELECT identity,data FROM operation_context_index ORDER BY ordinal', self._context)
        self['diagnostics'] = SqlSequence(self.conn, "SELECT data FROM records WHERE collection='diagnostics' ORDER BY ordinal", lambda row: bounded_json(row[0]))
        receipt_key=receipt
        receipt = (str(self.root), metadata['analysis_hash'], descriptor.stat().st_mtime_ns)
        proof=dict(map_root=str(self.root),manifest_hash=self.manifest_hash,analysis_hash=metadata['analysis_hash'])
        prior=None
        if receipt_key is not None:
            path=Path(receipt_key)
            if path.is_file() and path.stat().st_size<=65536:
                try:prior=bounded_json(path.read_text(encoding='utf-8'))
                except (ValueError,OSError):prior=None
        # Only a caller that just successfully ran the mapper may reuse its
        # write-time note digests. Imported notes are still checked when read.
        if validate_notes and not trusted_publication and receipt not in _validated and prior!=proof:
            for number, (path, expected) in enumerate(self.conn.execute('SELECT path,note_hash FROM notes ORDER BY path'), 1):
                if digest(self.safe_path(path)) != expected:
                    raise ValueError('Indexed note hash mismatch: ' + path)
                if progress and (number == 1 or number % 250 == 0):
                    progress(f'Validated {number} indexed notes: {path}')
            self._validate_links()
            if len(_validated)>=128:_validated.clear()
            _validated.add(receipt)
        else:
            self._validate_links()
        if validate_notes and receipt_key is not None and prior!=proof:
            path=Path(receipt_key);path.parent.mkdir(parents=True,exist_ok=True)
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as output:
                    output.write(json.dumps(proof));temporary=Path(output.name)
                temporary.replace(path)
            finally:
                if temporary is not None:temporary.unlink(missing_ok=True)

    def safe_path(self, relative):
        path = self.root / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or not path.resolve().is_relative_to(self.root):
            raise ValueError('Unsafe indexed map path: ' + relative)
        return path

    @staticmethod
    def _entry(row):
        return dict(bounded_json(row[0]), note_hash=row[1])

    def entry(self, note):
        row = self.conn.execute('SELECT data,note_hash FROM notes WHERE path=? AND definition IS NOT NULL', (note,)).fetchone()
        if row is None:
            raise ValueError('Missing indexed note: ' + note)
        return self._entry(row)

    def consumers(self, definition):
        """Page qualified consumer identities without embedding a global array in each note."""
        return SqlSequence(self.conn,'SELECT context FROM note_consumers WHERE definition=? ORDER BY context',lambda row:row[0],(definition,))

    def _context(self, row):
        identity, data = row
        size=self.conn.execute('SELECT COALESCE(sum(length(CAST(data AS BLOB))+length(key)+128),0) FROM context_parts WHERE context=?',(identity,)).fetchone()[0]
        if size+len(data.encode('utf-8'))>MAX_RECORD_BYTES:
            raise ValueError('Selected operation context exceeds the 4 MiB materialization budget: '+identity)
        context = bounded_json(data)
        for kind in ('references', 'transition_targets'):
            context[kind] = {key: bounded_json(value)['value'] for key, value in self.conn.execute(
                'SELECT key,data FROM context_parts WHERE context=? AND kind=? ORDER BY key', (identity, kind))}
        for kind in ('step_notes', 'calls', 'java_resolution'):
            context[kind] = [bounded_json(value)['value'] for (value,) in self.conn.execute(
                'SELECT data FROM context_parts WHERE context=? AND kind=? ORDER BY CAST(key AS INTEGER)', (identity, kind))]
        return context

    def _validate_links(self):
        if self.conn.execute('''SELECT b.note FROM context_bindings b LEFT JOIN notes n ON n.path=b.note
            WHERE n.definition IS NULL LIMIT 1''').fetchone():
            raise ValueError('Indexed context refers to a missing canonical note')
        if self.conn.execute('''SELECT c.target FROM context_calls c LEFT JOIN operation_context_index o
            ON o.channel||'/'||o.name=c.target WHERE COALESCE(c.detail,'')='' AND o.identity IS NULL LIMIT 1''').fetchone():
            raise ValueError('Indexed operation call has no execution context')

    def verify_sources(self, root, progress=None):
        """Reject stale maps before selected evidence can become a ready run."""
        root = Path(root).resolve()
        for number, (relative, expected) in enumerate(self.conn.execute('SELECT relative_path,hash FROM files ORDER BY path'), 1):
            path = root / relative
            if not path.resolve().is_relative_to(root) or not path.is_file() or digest(path) != expected:
                raise ValueError('Composer map is stale; source changed: ' + relative)
            if progress and number % 250 == 0:
                progress(f'Verified {number} source fingerprints; no source parsing')
        # Additions can change wildcard resolution even if existing files are identical.
        expected = self.conn.execute('SELECT count(*) FROM files').fetchone()[0]
        seen = 0
        skipped = {'ejb-jar.xml','web.xml','application.xml','application-client.xml','ra.xml','persistence.xml','beans.xml','faces-config.xml','validation.xml'}
        for path in root.rglob('*'):
            if path.is_file() and path.name.lower() not in skipped and (path.suffix.lower() in {'.java','.xml','.ini'} or path.name in {'.classpath','.project'}):
                seen += 1
                if not self.conn.execute('SELECT 1 FROM files WHERE relative_path=?', (path.relative_to(root).as_posix(),)).fetchone():
                    raise ValueError('Composer map is stale; source added: ' + str(path))
        if seen != expected:
            raise ValueError('Composer map source file set changed')

    def close(self):
        if getattr(self, 'conn', None) is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        self.close()


def is_indexed_map(root):
    """Probe only the small descriptor; legacy inventories stay on their existing reader."""
    path = Path(root) / 'vault-manifest.json'
    if not path.is_file() or path.stat().st_size > 65536:
        return False
    return bounded_json(path.read_text(encoding='utf-8-sig')).get('vault_schema_version') == 4
