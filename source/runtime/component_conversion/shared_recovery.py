"""Recover exact pinned publications from still-verified run artifacts without reconversion."""
import hashlib
import json
from pathlib import Path


def restore_from_run(store, conn, config, group_id, manifest):
    """Reconstruct only the exact pinned bytes; changed artifacts require explicit revalidation."""
    from tools.state_store_tools import component_records as records
    from tools.state_store_tools.behavior_units import snapshot
    from tools.shared_artifact_store.jars import compiled_jar
    from tools.shared_artifact_store.manifests import file_hash
    head = records.head(conn, config.run_id, group_id)
    if not head or head['status'] != 'component_validated':
        return None
    saved = records.read_record(conn, config.run_id, group_id, 'result', head['result_revision'])
    root = Path(next(iter(saved['results'].values()))['artifact_root'])
    bundle = snapshot(conn, config.run_id, 'component_generation', group_id)
    metadata = manifest['metadata']
    if bundle is None or bundle['status'] != 'accepted' or 'pom_content' not in metadata:
        return None
    from models.native_component_bundle import NativeComponentBundle
    files = {'bundle.json': NativeComponentBundle.model_validate_json(bundle['data_json']).model_dump_json().encode(),
             metadata['jar']: compiled_jar(root / 'target/classes', metadata['classes']),
             metadata['pom']: metadata['pom_content'].encode()}
    for name, expected in manifest['files'].items():
        if name.startswith('evidence/'):
            from tools.shared_artifact_store.manifests import contained_path
            files[name] = contained_path(root, name.removeprefix('evidence/'))
        source = files.get(name)
        if source is None:
            return None
        actual = hashlib.sha256(source).hexdigest() if isinstance(source, bytes) else file_hash(source)
        if actual != expected:
            return None
    directory, recovered = store.publish(manifest['lookup_key'], files, metadata)
    if recovered['revision'] != manifest['revision']:
        raise ValueError('Recovered component does not match its pinned revision')
    return directory, recovered
