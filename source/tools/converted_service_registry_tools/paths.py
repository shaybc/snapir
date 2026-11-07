"""Keep durable operation references relocatable while leaving API lookup independent of files."""
from copy import deepcopy
from pathlib import Path


def registry_directory(conn):
    """Locate this SQLite registry without depending on the current working directory."""
    path = conn.execute('PRAGMA database_list').fetchone()[2]
    return Path(path).resolve().parent if path else None


def service_paths(conn, record, *, relative=False):
    """Translate version-two artifact paths; legacy records retain their existing representation."""
    result = deepcopy(record)
    root = registry_directory(conn)
    if root is None or result.get('schema_version') != 'v2':
        return result
    references = [(result, 'artifact_reference'), (result['completion'], 'validation_report_reference')]
    evidence = result.get('api_definition', {}).get('artifact_evidence')
    if evidence:
        references.append((evidence, 'root'))
    for owner, name in references:
        path = Path(owner[name])
        if relative and path.is_absolute() and path.resolve().is_relative_to(root):
            owner[name] = path.resolve().relative_to(root).as_posix()
        elif not relative and not path.is_absolute():
            from tools.shared_artifact_store.manifests import contained_path
            owner[name] = str(contained_path(root, owner[name]))
    return result
