"""Readable copied-source paths from indexed Java packages and source project ownership."""
from collections import defaultdict
from pathlib import Path, PurePosixPath
import re


def _package_path(original, names):
    """Use a top-level indexed type's package, retaining the original compilation-unit filename."""
    if not names:
        raise ValueError('Source package has no indexed class evidence: ' + original)
    # Nested type names have extra components; every top-level type in a file has the same package.
    top_level = min(names, key=lambda name: (name.count('.'), name))
    package = top_level.rpartition('.')[0]
    parts = package.split('.') if package else []
    if any(not part or part in {'.', '..'} or '/' in part or '\\' in part for part in parts):
        raise ValueError('Invalid indexed Java package: ' + package)
    return PurePosixPath(*parts, Path(original).name).as_posix()


def _project_labels(projects):
    """Use project names, extending with readable ancestors when names would collide."""
    parts = {}
    for project in projects:
        values = PurePosixPath(project.replace('\\', '/')).parts
        parts[project] = [re.sub(r'[^\w.-]', '_', value).strip('. ') or 'project'
                          for value in values if value not in {'/', ''}]
        if not parts[project]:
            parts[project] = ['project']
    depth = {project: 1 for project in projects}
    while True:
        labels = {project: '--'.join(parts[project][-depth[project]:]) for project in projects}
        duplicates = defaultdict(list)
        for project, label in labels.items():
            duplicates[label.casefold()].append(project)
        collisions = [group for group in duplicates.values() if len(group) > 1]
        if not collisions:
            return labels
        for group in collisions:
            if all(depth[project] >= len(parts[project]) for project in group):
                raise ValueError('Source project names cannot be distinguished safely: ' + ', '.join(sorted(group)))
            for project in group:
                depth[project] += 1


def copied_source_paths(source_files, file_classes, classes):
    """Prefix only colliding package/file paths with readable project folders; never use hashes."""
    packages, owners = {}, {}
    by_package = defaultdict(list)
    for original in source_files:
        names = file_classes[original]
        packages[original] = _package_path(original, names)
        projects = {classes[name]['project'] for name in names}
        if len(projects) != 1 or not next(iter(projects)):
            raise ValueError('Source file has no unique project owner: ' + original)
        owners[original] = next(iter(projects))
        # Detect Windows collisions even when preparation happens on another OS.
        by_package[packages[original].casefold()].append(original)
    colliding = {original for group in by_package.values() if len(group) > 1 for original in group}
    labels = _project_labels({owners[original] for original in colliding})
    result, used = {}, {}
    for original in source_files:
        # A hyphen distinguishes this prefix from a legal Java package component.
        prefix = 'project-' + labels[owners[original]] + '/' if original in colliding else ''
        relative = 'sources/' + prefix + packages[original]
        key = relative.casefold()
        if key in used:
            raise ValueError('Source files in the same project collide: ' + used[key] + ' and ' + original)
        used[key] = original
        result[original] = relative
    return result
