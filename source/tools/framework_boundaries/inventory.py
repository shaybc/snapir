"""Inventory explicit framework archives without loading classes or extracting source."""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile, BadZipFile
import hashlib

_current = ContextVar('framework_inventory', default={})


@lru_cache(maxsize=64)
def archive_classes(path, revision):
    """Cache an archive directory by verified content hash, including multi-release classes."""
    result = set()
    try:
        with ZipFile(path) as archive:
            for entry in archive.namelist():
                if entry.startswith('META-INF/versions/'):
                    parts = entry.split('/', 3)
                    if len(parts) != 4 or not parts[2].isdigit(): continue
                    entry = parts[3]
                if entry.endswith('.class') and not entry.startswith('META-INF/'):
                    name = entry[:-6].replace('/', '.')
                    if name.rsplit('.', 1)[-1] not in {'module-info', 'package-info'}:
                        result.add(name)
    except (OSError, BadZipFile) as error:
        raise ValueError('Invalid framework JAR: ' + path) from error
    return tuple(sorted(result))


def scan(paths):
    """Return exact class ownership; reject ambiguous archives instead of guessing precedence."""
    result = {}
    seen = set()
    for value in paths:
        path = Path(value).resolve()
        if path.suffix.lower() != '.jar' or not path.is_file():
            raise ValueError('Framework JAR must be an existing archive: ' + str(path))
        with path.open('rb') as stream: revision = hashlib.file_digest(stream, 'sha256').hexdigest()
        if revision in seen: continue
        seen.add(revision)
        for name in archive_classes(str(path), revision):
            if name in result:
                raise ValueError('Conflicting framework class ownership: ' + name)
            result[name] = dict(path=str(path), sha256=revision)
    return result


def current():
    """Read the run-local ownership view; never infer ownership from an IBM prefix."""
    return _current.get()


def owner(name):
    """Resolve binary nested-class spelling and exact supplied class membership."""
    entries = current()
    if not name: return None
    if name in entries: return entries[name]
    return next((value for key, value in entries.items() if key.replace('$', '.') == name), None)


@contextmanager
def framework_scope(paths):
    """Bind a validated immutable ownership snapshot to one conversion execution."""
    token = _current.set(scan(paths))
    try: yield current()
    finally: _current.reset(token)


def paths():
    """List original-runtime archives without copying their class inventory into model requests."""
    return sorted({item['path'] for item in current().values()})


def verify():
    """Reject framework binary changes during a conversion or comparison attempt."""
    for path, revision in {(item['path'], item['sha256']) for item in current().values()}:
        with Path(path).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != revision:
                raise ValueError('Framework JAR changed during execution: ' + path)
