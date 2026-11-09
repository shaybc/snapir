"""Read bounded Eclipse metadata and publish a run-local supplement to an older map."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree

RESOLVER_VERSION = 'eclipse-project-order-v2'


def read_metadata(path, workspace, evidence):
    """Capture one stable file, including absence, without altering the mapper database."""
    path, workspace = Path(path).resolve(), Path(workspace).resolve()
    if not path.is_relative_to(workspace):
        raise ValueError('Eclipse metadata escapes workspace: ' + str(path))
    key = str(path)
    if not path.exists():
        if key in evidence and evidence[key] is not None:
            raise ValueError('Eclipse metadata changed during resolution: ' + key)
        evidence[key] = None
        return None
    before = path.stat()
    with path.open('rb') as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError('Eclipse metadata exceeds 1 MiB: ' + str(path))
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Eclipse metadata changed while reading: ' + str(path))
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unsupported Eclipse metadata entity declaration: ' + str(path))
    digest = hashlib.sha256(data).hexdigest()
    if key in evidence and evidence[key] != digest:
        raise ValueError('Eclipse metadata changed during resolution: ' + key)
    evidence[key] = digest
    return ElementTree.fromstring(data)


def publish_supplement(workspace, index):
    """Publish diagnostic metadata evidence; freshness still compares current file hashes."""
    from tools.composer_mapper_tools.mapped_scope import current_mapped
    mapped = current_mapped(workspace)
    database = getattr(getattr(mapped, 'config', None), 'db_path', None)
    if not database:
        return
    directory = Path(database).resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    payload = dict(resolver=RESOLVER_VERSION, workspace=str(Path(workspace).resolve()),
                   files=index.metadata_fingerprints, containers=index.container_resolutions,
                   project_references=index.project_references,
                   project_classpaths={name: view.model_dump(mode='json') for name, view in index.project_classpaths.items()},
                   binary_resolutions=index.binary_resolutions)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, sort_keys=True, indent=2)
    try:
        os.replace(temporary, directory / 'eclipse-metadata.json')
    finally:
        temporary.unlink(missing_ok=True)
