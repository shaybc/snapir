"""Stable file identities and safe writes for tool-owned artifacts."""
import hashlib
import json
from pathlib import Path


def digest(value):
    """Return a stable JSON identity."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_hash(path):
    """Hash a file without loading its entire contents."""
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    """Read a local UTF-8 JSON record."""
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    """Atomically replace a tool-owned record."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def inside(root, relative):
    """Resolve a recorded relative path, rejecting traversal, symlinks outside root and drive paths."""
    from pathlib import PureWindowsPath
    relative = str(relative)
    if Path(relative).is_absolute() or PureWindowsPath(relative).drive or '\\' in relative:
        raise ValueError('Expected a relative forward-slash path: ' + relative)
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError('Path escapes its folder: ' + relative)
    return target
