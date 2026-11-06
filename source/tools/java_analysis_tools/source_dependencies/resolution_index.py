"""Spool immutable compatibility source-index metadata for the shared Java resolver."""

import atexit
from collections import OrderedDict
from pathlib import Path
import sqlite3
import tempfile
import weakref

_indexes=OrderedDict()


def resolution_index(index):
    """Capture one discovery result; callers replace indexes after source/visibility changes."""
    identity=id(index)
    cached=_indexes.get(identity)
    if cached and cached[0]() is index:
        _indexes.move_to_end(identity)
        return Path(cached[1].name)/'types.sqlite'
    if cached:
        # Python can reuse a collected index's ID while the JVM still holds its
        # database. Close that handle before dropping the temporary directory.
        from tools.java_analysis_tools.source_dependencies.resolution_process import _close_worker
        _close_worker()
        cached[1].cleanup()
        del _indexes[identity]
    temporary=tempfile.TemporaryDirectory(prefix='snapir-java-type-index-')
    path=Path(temporary.name)/'types.sqlite'
    try:
        conn=sqlite3.connect(path)
        try:
            conn.executescript('''PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;
                CREATE TABLE java_sources(file TEXT,fqcn TEXT,project TEXT,PRIMARY KEY(file,fqcn));
                CREATE INDEX type_names ON java_sources(fqcn);
                CREATE TABLE java_projects(name TEXT PRIMARY KEY,declared INTEGER);
                CREATE TABLE java_project_refs(project TEXT,target TEXT,PRIMARY KEY(project,target));''')
            conn.executemany('INSERT OR IGNORE INTO java_sources VALUES (?,?,?)',
                ((path,name,index.class_projects.get(path)) for name,paths in index.classes.items() for path in paths))
            conn.executemany('INSERT INTO java_projects VALUES (?,1)',((name,) for name in index.project_references))
            conn.executemany('INSERT OR IGNORE INTO java_project_refs VALUES (?,?)',
                ((name,target) for name,targets in index.project_references.items() for target in targets))
            conn.commit()
        finally:
            conn.close()
        try:
            reference=weakref.ref(index)
        except TypeError:
            reference=lambda:index
        _indexes[identity]=(reference,temporary)
        return path
    except BaseException:
        temporary.cleanup()
        raise


def release_old_indexes(active):
    """Keep only the active snapshot and at most one other bounded on-disk snapshot."""
    for identity,(_,temporary) in list(_indexes.items()):
        if len(_indexes)<=2:
            break
        if Path(temporary.name)/'types.sqlite'!=active:
            temporary.cleanup()
            del _indexes[identity]


def close_indexes():
    """Release captured metadata after the Java worker has closed its connection."""
    for _,temporary in _indexes.values():
        temporary.cleanup()
    _indexes.clear()


atexit.register(close_indexes)
