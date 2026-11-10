"""Bind supplied source evidence to verified, ordered project library views."""

from pathlib import Path
from zipfile import ZipFile, BadZipFile

from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.source_discovery_tools.binary_resolution import archive_digest, ordered_library_paths


def project_context(unit, boundary, origins, classpath):
    """Return native-machine absolute paths and per-source visibility, without scanning sources."""
    if classpath is None or not classpath.project_classpaths and not classpath.libraries:
        return {}
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
    if len(owners) != 1 or not next(iter(owners)):
        raise ValueError('Boundary implementation has no unique owning project: ' + str(boundary.implementation_class))
    projects = {}
    for project in sorted(set(source_projects.values())):
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
        roots = [Path(entry.path).resolve() for entry in entries if entry.kind == 'source']
        visible = [identity for identity, owner in source_projects.items() if owner == project or
                   any(Path(by_identity[identity]['source_file']).resolve().is_relative_to(root) for root in roots)]
        projects[project] = dict(libraries=libraries, visible_sources=sorted(visible))
    context = dict(project=next(iter(owners)), source_projects=source_projects, projects=projects)
    return dict(context, fingerprint=digest(context))
