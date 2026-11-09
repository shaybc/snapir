"""Materialize exact retained bytes in Maven layout and portable checksum manifests."""

import hashlib
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile
from models.retained_library import RetainedLibrary
from tools.shared_artifact_store.manifests import contained_path, file_hash
from tools.conversion_tools.composer_runtime_contracts import composer_class

DIRECTORY = 'retained-dependencies'


def class_name(entry):
    """Normalize ordinary and multi-release JAR class entries for vendor checks."""
    if entry.startswith('META-INF/versions/'):
        entry = entry.split('/', 3)[-1]
    return entry[:-6].replace('/', '.').replace('$', '.')


def archive_path(dependency, suffix):
    """Use validated Maven model coordinates, never filesystem paths from model output."""
    return '/'.join([dependency.group_id.replace('.', '/'), dependency.artifact_id, dependency.version,
                     dependency.artifact_id + '-' + dependency.version + '.' + suffix])


def verify_library(value, profile):
    """Verify class ownership, original bytes and IBM approval independently of wrapper identity."""
    library = RetainedLibrary.model_validate(value)
    path = Path(library.path)
    if not path.is_file() or file_hash(path) != library.sha256:
        raise ValueError('Retained library changed or is missing: ' + str(path))
    sidecar = path.with_suffix('.pom')
    if (file_hash(sidecar) if sidecar.is_file() else None) != library.pom_sha256:
        raise ValueError('Retained library Maven metadata changed: ' + str(sidecar))
    with ZipFile(path) as archive:
        names = {class_name(name) for name in archive.namelist() if name.endswith('.class')}
    if any(composer_class(name) for name in names):
        raise ValueError('Retained JAR contains prohibited Composer runtime classes: ' + str(path))
    if not set(library.dependency.required_classes) <= names:
        raise ValueError('Retained JAR does not contain its declared required classes')
    ibm = any(name.startswith('com.ibm.') for name in library.dependency.required_classes)
    if ibm and library.original_coordinates not in getattr(profile, 'allowed_ibm_artifacts', ()) and not all(
        name in getattr(profile, 'allowed_ibm_classes', ()) for name in library.dependency.required_classes):
        raise ValueError('Retained IBM library lacks original class/artifact approval')
    if ibm != library.ibm:
        raise ValueError('Retained library vendor classification changed')
    return library


def original_pom(library, repository):
    """Prefer the original or cached POM so Maven retains declared transitives and parents."""
    cached = contained_path(repository, archive_path(library.dependency, 'pom'))
    sidecar = Path(library.path).with_suffix('.pom')
    embedded = 'META-INF/maven/' + library.dependency.group_id + '/' + library.dependency.artifact_id + '/pom.xml'
    if cached.is_file():
        return cached.read_bytes()
    if sidecar.is_file() and library.pom_sha256 and library.original_coordinates == library.dependency.coordinates:
        return sidecar.read_bytes()
    with ZipFile(library.path) as archive:
        if embedded in archive.namelist() and library.original_coordinates == library.dependency.coordinates:
            return archive.read(embedded)
    root = ElementTree.Element('project', xmlns='http://maven.apache.org/POM/4.0.0')
    for key, value in [('modelVersion', '4.0.0'), ('groupId', library.dependency.group_id),
                       ('artifactId', library.dependency.artifact_id), ('version', library.dependency.version)]:
        ElementTree.SubElement(root, key).text = value
    return ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)


def _lock(directory):
    path = Path(directory) / 'dependencies.lock.json'
    if not path.exists():
        return dict(schema_version=1, files={}, libraries={})
    return verify_portable(directory)


def verify_portable(directory):
    """Reject missing/changed portable bytes before cache installation, copying or packaging."""
    directory = Path(directory)
    data = json.loads((directory / 'dependencies.lock.json').read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('files'), dict) or not isinstance(data.get('libraries'), dict):
        raise ValueError('Unsupported retained library manifest')
    for name, digest in data['files'].items():
        path = contained_path(directory, name)
        if path.is_symlink() or not path.is_file() or file_hash(path) != digest:
            raise ValueError('Portable retained dependency changed: ' + name)
    from models.maven_dependency import MavenDependency
    for coordinate, record in data['libraries'].items():
        parts = coordinate.split(':')
        if len(parts) != 3:
            raise ValueError('Invalid retained library coordinates')
        dependency = MavenDependency(group_id=parts[0], artifact_id=parts[1], version=parts[2], reason='Portable retained artifact')
        if data['files'].get('repository/' + archive_path(dependency, 'jar')) != record['sha256']:
            raise ValueError('Portable retained identity differs from original JAR')
    return data


def materialize(value, profile, project, repository):
    """Install one AI-selected retained library, without exporting unused candidates."""
    library = verify_library(value, profile)
    directory = Path(project) / DIRECTORY
    lock = _lock(directory)
    jar_name, pom_name = [archive_path(library.dependency, suffix) for suffix in ('jar', 'pom')]
    jar = contained_path(repository, jar_name)
    if jar.exists() and file_hash(jar) != library.sha256:
        raise ValueError('Maven coordinates resolve to different bytes than the selected original JAR: ' + library.dependency.coordinates)
    pom_bytes = original_pom(library, repository)
    for name, content in [(jar_name, Path(library.path)), (pom_name, pom_bytes)]:
        target = contained_path(directory, 'repository/' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, Path):
            shutil.copyfile(content, target)
        else:
            target.write_bytes(content)
        lock['files']['repository/' + name] = file_hash(target)
        cached = contained_path(repository, name)
        cached.parent.mkdir(parents=True, exist_ok=True)
        if cached.exists() and file_hash(cached) != file_hash(target):
            raise ValueError('Conflicting retained artifact cache entry: ' + name)
        if not cached.exists():
            shutil.copyfile(target, cached)
    lock['libraries'][library.dependency.coordinates] = dict(sha256=library.sha256,
        original_coordinates=library.original_coordinates, required_classes=library.dependency.required_classes, ibm=library.ibm)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'dependencies.lock.json').write_text(json.dumps(lock, sort_keys=True, indent=2), encoding='utf-8')
    from tools.shared_artifact_store.project_repository import attach_repository
    attach_repository(Path(project) / 'pom.xml', (), retained=True)


def restore_portable(source, destination, repository=None):
    """Restore a published retained repository without referring to its original workstation."""
    source, destination = Path(source), Path(destination)
    if not source.exists():
        return
    original = verify_portable(source)
    lock = _lock(destination)
    for name, digest in original['files'].items():
        if name in lock['files'] and lock['files'][name] != digest:
            raise ValueError('Conflicting portable retained artifacts: ' + name)
        target = contained_path(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.resolve() != contained_path(source, name).resolve():
            shutil.copyfile(contained_path(source, name), target)
        lock['files'][name] = digest
        if repository is not None and name.startswith('repository/'):
            cached = contained_path(repository, name.removeprefix('repository/'))
            cached.parent.mkdir(parents=True, exist_ok=True)
            if cached.exists() and file_hash(cached) != digest:
                raise ValueError('Retained Maven cache conflict: ' + name)
            if not cached.exists():
                shutil.copyfile(target, cached)
    for coordinate, value in original['libraries'].items():
        if coordinate in lock['libraries'] and lock['libraries'][coordinate] != value:
            raise ValueError('Retained library identity conflict: ' + coordinate)
        lock['libraries'][coordinate] = value
    destination.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        (destination / 'dependencies.lock.json').write_text(json.dumps(lock, sort_keys=True, indent=2), encoding='utf-8')


def capture_resolved(project, dependencies, repository):
    """Include resolved runtime/compile transitives once a retained dependency was selected."""
    directory = Path(project) / DIRECTORY
    if not directory.exists():
        return
    lock = verify_portable(directory)
    for dependency in dependencies:
        if dependency.scope in {'test', 'provided'} or dependency.group_id == 'il.co.dcd.converted':
            continue
        for suffix in ('jar', 'pom'):
            name = archive_path(dependency, suffix)
            original = contained_path(repository, name)
            if not original.is_file():
                raise ValueError('Resolved retained dependency artifact is unavailable: ' + name)
            if suffix == 'jar':
                with ZipFile(original) as archive:
                    if any(composer_class(class_name(item)) for item in archive.namelist() if item.endswith('.class')):
                        raise ValueError('Resolved retained dependency includes Composer runtime: ' + name)
            target = contained_path(directory, 'repository/' + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if 'repository/' + name in lock['files'] and file_hash(original) != lock['files']['repository/' + name]:
                raise ValueError('Resolved artifact differs from retained bytes: ' + name)
            shutil.copyfile(original, target)
            lock['files']['repository/' + name] = file_hash(target)
            if suffix == 'pom':
                from runtime.retained_libraries.pom_closure import metadata_dependencies
                for metadata_name, metadata_source in metadata_dependencies(repository, name).items():
                    metadata_target = contained_path(directory, 'repository/' + metadata_name)
                    metadata_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(metadata_source, metadata_target)
                    lock['files']['repository/' + metadata_name] = file_hash(metadata_target)
    (directory / 'dependencies.lock.json').write_text(json.dumps(lock, sort_keys=True, indent=2), encoding='utf-8')
