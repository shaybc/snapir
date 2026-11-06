"""Spool inventory collections to SQLite with canonical XML content and lazy readers."""

from collections.abc import MutableMapping, Sequence
import hashlib
import json
from pathlib import Path
import sqlite3
from xml.etree import ElementTree


class InventoryRecords:
    """Own one run's scratch inventory; each read materializes only one record."""

    def __init__(self, path, cache=None, selection=None):
        self.conn = sqlite3.connect(path, uri=True)
        self.conn.execute('PRAGMA cache_size=-8192')
        self.conn.execute('PRAGMA temp_store=FILE')
        self.conn.execute('CREATE TABLE IF NOT EXISTS records (collection TEXT, identity TEXT, data TEXT, PRIMARY KEY(collection,identity))')
        self.conn.execute('CREATE TABLE IF NOT EXISTS content (hash TEXT PRIMARY KEY, text TEXT)')
        self.cache = cache
        self.selection = selection
        self.progress = None

    def mapping(self, name, model):
        """Return a disk-backed identity mapping for validated model records."""
        return RecordMapping(self, name, model)

    def close(self):
        """Commit scratch evidence and release the file handle."""
        self.conn.commit()
        self.conn.close()


class RecordMapping(MutableMapping):
    """Deduplicate records by identity without retaining model objects or repeated XML."""

    def __init__(self, store, name, model):
        self.store, self.name, self.model = store, name, model

    def __setitem__(self, key, value):
        data = value.model_dump(mode='json')
        xml = data.pop('configuration_xml', None)
        if xml is not None:
            digest = hashlib.sha256(xml.encode()).hexdigest()
            self.store.conn.execute('INSERT OR IGNORE INTO content VALUES (?,?)', (digest, xml))
            data['_xml_content'] = digest
        self.store.conn.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)', (self.name, key, json.dumps(data)))

    def __getitem__(self, key):
        row = self.store.conn.execute('SELECT data FROM records WHERE collection=? AND identity=?', (self.name, key)).fetchone()
        if row is None:
            raise KeyError(key)
        data = json.loads(row[0])
        digest = data.pop('_xml_content', None)
        if digest is not None:
            data['configuration_xml'] = self.store.conn.execute('SELECT text FROM content WHERE hash=?', (digest,)).fetchone()[0]
        return self.model.model_validate(data)

    def __delitem__(self, key):
        self.store.conn.execute('DELETE FROM records WHERE collection=? AND identity=?', (self.name, key))

    def __iter__(self):
        return (row[0] for row in self.store.conn.execute('SELECT identity FROM records WHERE collection=? ORDER BY identity', (self.name,)))

    def __len__(self):
        return self.store.conn.execute('SELECT count(*) FROM records WHERE collection=?', (self.name,)).fetchone()[0]

    def values(self):
        """Yield one hydrated model at a time in stable identity order."""
        for key in self:
            yield self[key]


class RecordSequence(Sequence):
    """Expose ordered database records to existing iteration-based consumers."""

    def __init__(self, mapping):
        self.mapping = mapping

    def __len__(self):
        return len(self.mapping)

    def __iter__(self):
        return self.mapping.values()

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        row = self.mapping.store.conn.execute('SELECT identity FROM records WHERE collection=? ORDER BY identity LIMIT 1 OFFSET ?',
            (self.mapping.name, index)).fetchone()
        if row is None:
            raise IndexError(index)
        return self.mapping[row[0]]


class DefinitionCatalog:
    """Store XML definition bodies on disk and index lookups by kind and logical name."""

    def __init__(self, store):
        self.conn = store.conn
        self.conn.execute('CREATE TABLE IF NOT EXISTS xml_definitions (ordinal INTEGER PRIMARY KEY, kind TEXT, name TEXT, data TEXT, xml TEXT)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS xml_definition_names ON xml_definitions(kind,name)')

    def append(self, definition):
        data = {key: value for key, value in definition.items() if key not in {'node', 'selectors'}}
        data['path'] = str(data['path'])
        data['_tail'] = definition['node'].tail
        self.conn.execute('INSERT INTO xml_definitions(kind,name,data,xml) VALUES (?,?,?,?)',
            (data['kind'], data['logical_id'], json.dumps(data), ElementTree.tostring(definition['node'], encoding='unicode')))

    def _read(self, rows):
        from tools.component_inventory_tools.xml_documents import walk_nodes
        for data, xml in rows:
            value = json.loads(data)
            value['path'] = Path(value['path'])
            value['node'] = ElementTree.fromstring(xml)
            value['node'].tail = value.pop('_tail', None)
            value['selectors'] = {id(node): selector for node, selector in walk_nodes(value['node'], value['selector'])}
            yield value

    def __iter__(self):
        return self._read(self.conn.execute('SELECT data,xml FROM xml_definitions ORDER BY ordinal'))

    def __len__(self):
        return self.conn.execute('SELECT count(*) FROM xml_definitions').fetchone()[0]

    def operations(self):
        """Read operation bodies without reloading every format/context/step definition."""
        return self._read(self.conn.execute("SELECT data,xml FROM xml_definitions WHERE kind='operation' ORDER BY ordinal"))

    def operation_count(self):
        """Count roots using the metadata index, without hydrating XML."""
        return self.conn.execute("SELECT count(*) FROM xml_definitions WHERE kind='operation'").fetchone()[0]

    def find(self, kind, name):
        """Load only matching definitions when following configured references."""
        return list(self._read(self.conn.execute('SELECT data,xml FROM xml_definitions WHERE kind=? AND name=? ORDER BY ordinal', (kind, name))))

    def resolve(self, kind, name, owner, scopes):
        """Resolve ownership using metadata first; never hydrate an ambiguous candidate set."""
        clause = 'kind=? AND name=?'
        parameters = (kind, name)
        local = clause + " AND json_extract(data,'$.path')=?"
        if self.conn.execute('SELECT 1 FROM xml_definitions WHERE ' + local + ' LIMIT 1', (*parameters, str(owner['path']))).fetchone():
            clause, parameters = local, (*parameters, str(owner['path']))
        elif owner['channel']:
            same = clause + " AND json_extract(data,'$.channel')=?"
            if self.conn.execute('SELECT 1 FROM xml_definitions WHERE ' + same + ' LIMIT 1', (*parameters, owner['channel'])).fetchone():
                clause, parameters = same, (*parameters, owner['channel'])
            else:
                clause += " AND (json_extract(data,'$.channel') IS NULL OR json_extract(data,'$.channel') IN (SELECT value FROM json_each(?)))"
                parameters = (*parameters, json.dumps(scopes.get(owner['channel'], [])))
        count = self.conn.execute('SELECT count(*) FROM xml_definitions WHERE ' + clause, parameters).fetchone()[0]
        if count != 1:
            return None, ('Missing' if count == 0 else 'Ambiguous') + ' ' + kind + ' reference: ' + name
        return next(self._read(self.conn.execute('SELECT data,xml FROM xml_definitions WHERE ' + clause, parameters))), None


class DiagnosticRecords(Sequence):
    """Deduplicate diagnostics on disk so unresolved workspace references cannot fill RAM."""

    def __init__(self, storage):
        self.conn = storage.conn
        self.conn.execute('CREATE TABLE IF NOT EXISTS inventory_diagnostics (message TEXT PRIMARY KEY)')

    def append(self, message):
        self.conn.execute('INSERT OR IGNORE INTO inventory_diagnostics VALUES (?)', (message,))

    def extend(self, messages):
        self.conn.executemany('INSERT OR IGNORE INTO inventory_diagnostics VALUES (?)', ((message,) for message in messages))

    def __iter__(self):
        return (row[0] for row in self.conn.execute('SELECT message FROM inventory_diagnostics ORDER BY message'))

    def __len__(self):
        return self.conn.execute('SELECT count(*) FROM inventory_diagnostics').fetchone()[0]

    def __getitem__(self, index):
        row = self.conn.execute('SELECT message FROM inventory_diagnostics ORDER BY message LIMIT 1 OFFSET ?', (index,)).fetchone()
        if row is None:
            raise IndexError(index)
        return row[0]
