"""Restore generated Maven artifacts from immutable publications without AI conversion."""
from pathlib import Path
import shutil
import tempfile
import logging

from tools.shared_artifact_store.manifests import contained_path, read_manifest


def repository_files(directory, manifest):
    """Map one published generated artifact to its standard Maven repository layout."""
    metadata = manifest['metadata']
    coordinates = metadata['coordinates']
    prefix = '/'.join([coordinates['group_id'].replace('.', '/'), coordinates['artifact_id'], coordinates['version']])
    basename = coordinates['artifact_id'] + '-' + coordinates['version']
    return {prefix + '/' + basename + '.' + suffix: contained_path(directory, metadata[suffix]) for suffix in ('jar', 'pom')}


def install_artifact(directory, manifest, profile, *, visited=None):
    """Populate derived and effective Maven caches from checksum-verified generated artifacts."""
    from tools.shared_artifact_store.location import store_root
    from tools.maven_dependency_tools.import_ownership import repository_path
    from tools.conversion_tools.scoped_reuse.fingerprints import revision
    read_manifest(directory)
    visited = set() if visited is None else visited
    if manifest['revision'] in visited:
        return
    visited.add(manifest['revision'])
    from tools.shared_artifact_store.storage import ArtifactStore
    with ArtifactStore(store_root(profile), 'components') as store:
        for dependency in manifest['metadata'].get('generated_dependencies', []):
            found = store.find(dependency['key'], revision=dependency['revision'])
            if found is None:
                raise ValueError('Pinned generated Maven dependency is unavailable')
            install_artifact(*found, profile, visited=visited)
    settings = getattr(profile, 'maven_settings_path', None)
    local = repository_path(settings, revision(settings) if settings else None, getattr(profile, 'maven_local_repository', None))
    for root in {store_root(profile) / 'maven-repository', Path(local)}:
        for name, source in repository_files(directory, manifest).items():
            target = contained_path(root, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                from tools.shared_artifact_store.manifests import file_hash
                if file_hash(target) == file_hash(source):
                    continue
                logging.getLogger(__name__).warning('Restoring changed generated Maven cache entry: %s', name)
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.shared-', delete=False) as stream:
                temporary = Path(stream.name)
            try:
                shutil.copyfile(source, temporary)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
