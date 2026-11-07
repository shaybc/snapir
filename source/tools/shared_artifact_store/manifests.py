"""Verify immutable artifact manifests and paths before indexing or consumption."""
import hashlib
import json
from pathlib import Path, PurePosixPath


def content_hash(value):
    """Hash structured semantic content deterministically."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def file_hash(path):
    """Hash a file without retaining large JARs in memory."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def contained_path(root, name):
    """Reject traversal, external links and platform-dependent artifact paths."""
    relative = PurePosixPath(name)
    root = Path(root).resolve()
    if not name or '\\' in name or ':' in name or relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe shared artifact path')
    path = root / name
    if not path.resolve().is_relative_to(root) or any(parent.is_symlink() for parent in [path, *path.parents] if parent != root):
        raise ValueError('Shared artifact path escapes its root')
    return path


def read_manifest(directory, *, verify=True):
    """Read a completed manifest; missing or altered evidence cannot become a hit."""
    directory = Path(directory)
    data = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    revision = data.get('revision')
    identity = {key: value for key, value in data.items() if key != 'revision'}
    if data.get('schema_version') != 1 or revision != content_hash(identity) or data.get('status') != 'approved' or data.get('metadata', {}).get('validated') is not True:
        raise ValueError('Shared artifact manifest is incomplete or changed')
    if directory.name != revision or not data.get('files'):
        raise ValueError('Shared artifact revision does not match its directory')
    if verify:
        for name, expected in data['files'].items():
            if file_hash(contained_path(directory, name)) != expected:
                raise ValueError('Shared artifact bytes changed: ' + name)
    return data
