"""Reject library shadowing between the trusted harness and native runtime JARs."""
import hashlib
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile


@lru_cache(maxsize=24)
def _classes(path,content_hash):
    with ZipFile(path) as archive:
        return {name:hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()
                if name.endswith('.class') and not name.endswith('module-info.class') and not name.startswith('META-INF/')}


def verify_runtime_dependencies(tool,classpath):
    """Conflicting class bytes must not silently execute the harness's dependency version."""
    def inventory(path):
        p=Path(path).resolve()
        return _classes(str(p),hashlib.sha256(p.read_bytes()).hexdigest())
    trusted=inventory(tool)
    for path in classpath:
        candidate=inventory(path)
        conflicts=[name for name in trusted.keys() & candidate.keys() if trusted[name]!=candidate[name]]
        if conflicts:raise ValueError('Harness/native dependency conflict; align the shared dependency policy and rebuild the harness: '+', '.join(sorted(conflicts)[:5]))
