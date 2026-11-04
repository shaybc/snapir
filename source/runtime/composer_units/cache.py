"""Verify immutable packages and original revisions before every reuse or execution."""
import hashlib
from pathlib import Path
from models.composer_unit_manifest import ComposerUnitManifest


def file_hash(path):
    """Hash exact bytes without text or line-ending normalization."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(root):
    """Reject changed/missing/extra package files, symlinks escaping the root, and stale originals."""
    root=Path(root).resolve();manifest=ComposerUnitManifest.model_validate_json((root/'manifest.json').read_text())
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='manifest.json'}
    if actual!=set(manifest.files):raise ValueError('Composer package file set changed')
    for name,expected in manifest.files.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or file_hash(path)!=expected:raise ValueError('Composer package file changed: '+name)
    for name,expected in manifest.originals.items():
        if file_hash(name)!=expected:raise ValueError('Original Composer input changed: '+name)
    return manifest
