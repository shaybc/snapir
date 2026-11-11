"""Bind supplied source evidence to verified, ordered project library views."""

import hashlib
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.source_discovery_tools.binary_resolution import archive_digest, ordered_library_paths


def project_context(unit, boundary, origins, classpath, *, original_classpath=()):
    """Return native-machine absolute paths and per-source visibility, without scanning sources."""
    from tools.framework_boundaries.inventory import paths as framework_paths
    framework = framework_paths()
    from tools.framework_boundaries.inventory import verify
    verify()
    if classpath is None or not classpath.project_classpaths and not classpath.libraries:
        selected = list(dict.fromkeys([*(str(Path(value).resolve()) for value in original_classpath), *framework]))
        if not selected: return {}
        libraries = [dict(path=value, sha256=_archive_hash(value)) for value in selected]
        _verify_framework_ownership(libraries, framework)
        context = dict(project='framework-comparison', source_projects={source['identity']: 'framework-comparison' for source in unit['sources']},
            projects={'framework-comparison': dict(libraries=libraries, visible_sources=[source['identity'] for source in unit['sources']])})
        return dict(context, fingerprint=digest(context))
    if not classpath.project_classpaths:
        raise ValueError('Boundary analysis requires verified project classpath ordering, not a global JAR list')
    by_identity = {origin['definition_id']: origin for origin in origins if origin.get('status') == 'verified_source'}
    source_projects = {}
    for source in unit['sources']:
        origin = by_identity.get(source['identity'], {})
        project = origin.get('source_project')
        if not project or project not in classpath.project_classpaths:
            raise ValueError('Boundary source has no verified owning project: ' + source['identity'])
        source_projects[source['identity']] = project
    owners = {origin.get('source_project') for origin in by_identity.values()
              if origin.get('fqcn') == boundary.implementation_class}
    if not owners:
        from tools.framework_boundaries.inventory import owner
        if owner(boundary.implementation_class):
            owners = {origin.get('profile_project') for origin in origins if origin.get('fqcn')==boundary.implementation_class and origin.get('profile_project')}
            if not owners and len(set(source_projects.values()))==1:
                owners = set(source_projects.values())
    if len(owners) != 1 or not next(iter(owners)):
        raise ValueError('Boundary implementation has no unique owning project: ' + str(boundary.implementation_class))
    projects = {}
    for project in sorted(set(source_projects.values()) | owners):
        entries = classpath.project_classpaths[project].entries
        libraries = []
        for value in ordered_library_paths(classpath, project):
            path = Path(value)
            if not path.is_absolute():
                raise ValueError('Boundary JAR path is not absolute for project ' + project + ': ' + value)
            try:
                path = path.resolve(strict=True)
                if not path.is_file():
                    raise OSError('not a file')
                revision = archive_digest(classpath, 'jar:' + str(path))
                with ZipFile(path) as archive:
                    archive.infolist()
            except (OSError, BadZipFile) as error:
                raise ValueError('Boundary JAR missing, unreadable or invalid for project ' + project + ': ' + value) from error
            libraries.append(dict(path=str(path), sha256=revision))
        existing = {item['path'] for item in libraries}
        for value in framework:
            if value not in existing:
                libraries.append(dict(path=value, sha256=_archive_hash(value)))
        _verify_framework_ownership(libraries, framework)
        roots = [Path(entry.path).resolve() for entry in entries if entry.kind == 'source']
        visible = [identity for identity, owner in source_projects.items() if owner == project or
                   any(Path(by_identity[identity]['source_file']).resolve().is_relative_to(root) for root in roots)]
        projects[project] = dict(libraries=libraries, visible_sources=sorted(visible))
    context = dict(project=next(iter(owners)), source_projects=source_projects, projects=projects)
    return dict(context, fingerprint=digest(context))


def _archive_hash(path):
    """Hash original binary evidence without retaining archive contents in memory."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _verify_framework_ownership(libraries, framework):
    """A configured ownership label cannot override a competing binary on the original classpath."""
    from tools.framework_boundaries.inventory import current, archive_classes
    if not current(): return
    for library in libraries:
        if library['path'] in framework or library['sha256'] in {item['sha256'] for item in current().values()}: continue
        conflicts = set(archive_classes(library['path'], library['sha256'])) & current().keys()
        if conflicts:
            raise ValueError('Framework class is also supplied by an unconfigured JAR: ' + sorted(conflicts)[0])
