"""Recover published APIs from complete durable operation snapshots."""
from pathlib import Path


def recover_services(conn, database_path):
    """Rebuild missing service rows without inspecting deployed services or original run folders."""
    from tools.shared_artifact_store.storage import ArtifactStore
    from runtime.operation_reuse.publication import materialize_contract
    from tools.converted_service_registry_tools.registry import publish_service
    database = Path(database_path).resolve()
    if database.parent.name != 'operations':
        return
    root = database.parent.parent
    if not (root / 'store.json').is_file():
        return
    with ArtifactStore(root, 'operations') as store:
        store.recover_index()
        publications = []
        for relative, in store.conn.execute('SELECT path FROM artifacts ORDER BY rowid').fetchall():
            from tools.shared_artifact_store.manifests import contained_path, read_manifest
            path = contained_path(store.directory, relative)
            try:
                manifest = read_manifest(path)
                if manifest['metadata'].get('api_published'):
                    publications.append((manifest['metadata'].get('published_at', ''), path, manifest))
            except (OSError, ValueError):
                # The generic index retains unavailable artifacts for diagnosis; they cannot be republished.
                continue
        for published_at, path, manifest in sorted(publications, key=lambda item: (item[0], item[2]['revision'])):
            service = publish_service(conn, materialize_contract(path, manifest))
            if published_at:
                with conn:
                    conn.execute('UPDATE converted_operation_services SET published_at=? WHERE application_id=? AND channel=? AND operation_id=? AND api_revision=?',
                        (published_at, service.application_id, service.channel, service.operation_id, service.api_revision))
