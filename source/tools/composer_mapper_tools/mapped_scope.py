"""Bind reusable map facts to one intake/resume without changing legacy discovery APIs."""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from xml.etree import ElementTree

_current = ContextVar('mapped_analysis_scope', default=None)


def current_mapped(workspace=None):
    """Return only the map explicitly bound to this run and source workspace."""
    mapped = _current.get()
    return mapped if mapped is not None and (workspace is None or Path(workspace).resolve() == mapped.workspace) else None


@contextmanager
def mapped_scope(mapped):
    """Use the same captured facts in downstream discovery, syntax and XML consumers."""
    token = _current.set(mapped)
    try:
        yield mapped
    finally:
        _current.reset(token)


def source_syntax(mapped, paths):
    """Yield one captured source document; never invoke javac or reopen Java source."""
    for path in paths:
        relative = Path(path).resolve().relative_to(mapped.workspace).as_posix()
        original = str(mapped.analysis.source_root / relative)
        source = ElementTree.Element('source', path=str(Path(path).resolve()))
        size = 0
        for kind, name, value, extra in mapped.analysis.conn.execute('SELECT kind,name,value,extra FROM java_facts WHERE file=? ORDER BY ordinal', (original,)):
            if kind.startswith('metadata:'):
                continue
            size += len(kind) + len(name or '') + len(value or '') + len(extra or '')
            if size * 4 > 4 * 1024 * 1024:
                raise ValueError('Captured Java syntax exceeds the materialization budget: ' + relative)
            if kind == 'package':
                source.set('package', value)
            elif kind == 'reference':
                ElementTree.SubElement(source, kind, name=name, kind=value, offset=extra)
            elif kind == 'import':
                ElementTree.SubElement(source, kind, name=name, static=value)
            else:
                ElementTree.SubElement(source, kind, name=name)
        if not source.get('package') and not len(source):
            raise ValueError('Java syntax was not captured by the map: ' + relative)
        yield source


def source_xml(mapped, path, selector=None):
    """Materialize one selected XML subtree using captured ordered node facts."""
    relative = Path(path).resolve().relative_to(mapped.workspace).as_posix()
    original = str(mapped.analysis.source_root / relative)
    if selector is None:
        row = mapped.analysis.conn.execute('SELECT id,selector FROM xml_nodes WHERE file=? AND parent IS NULL', (original,)).fetchone()
    else:
        row = mapped.analysis.conn.execute('SELECT id,selector FROM xml_nodes WHERE file=? AND selector=?', (original,selector)).fetchone()
    if row is None:
        raise ValueError('XML occurrence was not captured by the map: ' + relative + str(selector or ''))
    return mapped.definitions.hydrate(dict(node_id=row[0],selector=row[1],path=Path(path),kind='',logical_id='',channel=None))['node']
