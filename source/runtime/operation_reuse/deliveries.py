"""Archive final approved operation forms without claiming they are deployed."""
from pathlib import Path

from runtime.operation_layout import operation_repository
from tools.shared_artifact_store.location import application_id, store_root
from tools.shared_artifact_store.manifests import contained_path, content_hash
from tools.shared_artifact_store.storage import ArtifactStore


def preserve_deliveries(profile, directory, evidence, inventory):
    """Persist standalone and optional microservice artifacts only after the final gate approves."""
    by_key = {(item['channel'], item['operation_id']): item for item in evidence}
    with ArtifactStore(store_root(profile), 'operations') as store:
        for item in inventory['operations']:
            if item['blockers']:
                continue
            original = by_key[(item['channel'], item['operation_id'])]
            repository = operation_repository(original['project'])
            files = {'delivery/' + name.replace('\\', '/'): contained_path(directory, name.replace('\\', '/')) for name in item['files']}
            for path in repository.rglob('*'):
                if path.is_file() and not path.is_symlink():
                    relative = path.relative_to(repository)
                    if not any(part in {'.git','target','.demo-runtime'} or part.endswith('.PKG') for part in relative.parts) and path.name not in {'runtime-config.json','.env'}:
                        files['project/' + relative.as_posix()] = path
            key = content_hash([application_id(profile), item['channel'], item['operation_id']])
            store.publish(key, files, dict(validated=True, application_id=application_id(profile),
                channel=item['channel'], operation_id=item['operation_id'], standalone_validated=True,
                microservice_validated=bool(profile.microservice.enabled), api_published=False))
