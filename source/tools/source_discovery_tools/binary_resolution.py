"""Select binary origins only within a project's evidenced effective build path."""
from pathlib import Path
from tools.shared_artifact_store.manifests import file_hash


def archive_digest(index, location):
    """Hash each tied archive once per immutable discovery snapshot."""
    path = Path(location[4:])
    stat = path.stat()
    revision = (stat.st_size, stat.st_mtime_ns)
    previous = index._archive_hashes.get(location)
    if previous:
        if previous[0] != revision:
            raise ValueError('Archive changed during ordered resolution: ' + str(path))
        return previous[1]
    digest = file_hash(path)
    after = path.stat()
    if revision != (after.st_size, after.st_mtime_ns):
        raise ValueError('Archive changed during ordered resolution: ' + str(path))
    index._archive_hashes[location] = (revision, digest)
    return digest


def binary_choice(index, name, project, *, positions=None):
    """Return the first visible definition, retaining unresolved provider-order ties."""
    locations = index.classes.get(name, [])
    view = index.project_classpaths.get(project)
    if view is None:
        return dict(project=project, class_name=name, status='legacy_inventory', locations=locations, shadowed=[])
    if positions is None:
        positions = {entry.path: entry for entry in view.entries if entry.kind == 'library'}
    jars = sorted((location for location in locations if location.startswith('jar:') and location[4:] in positions),
                  key=lambda location: positions[location[4:]].rank)
    platform = [location for location in locations if location.startswith('jdk:')]
    chosen, status = [], 'missing'
    if jars:
        first = positions[jars[0][4:]]
        chosen = [location for location in jars if positions[location[4:]].rank == first.rank]
        if len(chosen) > 1:
            # Equal whole archives are interchangeable; matching class names alone are not.
            hashes = {archive_digest(index, location) for location in chosen}
            if len(hashes) == 1:
                chosen = chosen[:1]
        status = 'selected' if len(chosen) == 1 else 'unestablished_container_order'
    if platform:
        chosen = [*chosen, *platform]
        status = 'platform' if not jars and len(platform) == 1 else 'platform_binary_conflict'
    return dict(project=project, class_name=name, status=status, locations=chosen,
        shadowed=[location for location in jars if location not in chosen],
        precedence=[positions[location[4:]].model_dump(mode='json') for location in chosen if location.startswith('jar:')])


def classpath_for_project(index, project):
    """Keep the global inventory intact; expose one project view to existing consumers."""
    if index is None or not project or not getattr(index, 'project_classpaths', None) or index.active_project == project:
        return index
    if project not in index.project_classpaths:
        raise ValueError('Ordered classpath is unavailable for project: ' + project)
    if project in index._project_views:
        return index._project_views[project]
    positions = {entry.path: entry for entry in index.project_classpaths[project].entries if entry.kind == 'library'}
    choices = [binary_choice(index, name, project, positions=positions) for name in index.classes]
    result = index.model_copy(update={'classes': {item['class_name']: item['locations'] for item in choices if item['locations']},
        'libraries': [entry.path for entry in index.project_classpaths[project].entries if entry.kind == 'library'],
        'binary_resolutions': [choice for choice in choices if choice['shadowed'] or len(choice['locations']) > 1],
        'active_project': project})
    index._project_views[project] = result
    return result


def ordered_library_paths(index, project):
    """Use the existing expanded sequence, including unspecified container-internal order."""
    if not index.project_classpaths:
        return list(index.libraries)
    if project not in index.project_classpaths:
        raise ValueError('Original comparison needs an unambiguous source project')
    entries = [entry for entry in index.project_classpaths[project].entries if entry.kind == 'library']
    return [entry.path for entry in entries]
