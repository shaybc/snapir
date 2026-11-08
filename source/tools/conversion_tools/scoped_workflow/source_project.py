"""Resolve a consuming channel's production project from declared workspace ownership."""
from pathlib import Path
from xml.etree import ElementTree


def scoped_source_project(profile, channel, *, source_root=None, source_index=None):
    """Honor overrides, otherwise prove registry ownership using source-project metadata.

    An imported format's declaring project is not the consuming channel's project.
    Multiple possible owners remain unresolved instead of choosing by class name.
    """
    explicit = (getattr(profile, 'scoped_java_projects', None) or {}).get(
        channel, getattr(profile, 'scoped_java_project', None))
    if explicit:
        return explicit
    root = source_root or getattr(profile, 'source_root', None)
    if not root or not Path(root).is_dir():
        return None
    from tools.source_discovery_tools import discover_java_sources
    index = source_index if source_index is not None else discover_java_sources(root)
    if len(index.source_roots) == 1:
        return next(iter(index.source_roots))
    from tools.composer_mapper_tools.mapped_scope import current_mapped
    mapped = current_mapped(root)
    if mapped is not None:
        projects = {name: Path(mapped.location(path)).resolve() for name, path in
            mapped.analysis.conn.execute('SELECT name,path FROM java_projects') if name in index.source_roots}
        registries = [Path(mapped.location(path)).resolve() for (path,) in mapped.analysis.conn.execute(
            "SELECT path FROM files WHERE channel=? AND (lower(relative_path) LIKE '%/dse.ini' OR lower(relative_path) LIKE '%/dsc.ini' OR lower(relative_path) IN ('dse.ini','dsc.ini'))", (channel,))]
    else:
        projects = _project_directories(Path(root).resolve(), index)
        from tools.conversion_tools.scoped_reuse.evidence import source_layout
        registries = [Path(root).resolve() / name for name in source_layout(root).get('registries', {}).get(channel, {})]
    owners = set()
    for path in registries:
        candidates = [(len(directory.parts), name) for name, directory in projects.items() if path.is_relative_to(directory)]
        if candidates:
            depth = max(item[0] for item in candidates)
            owners.update(name for length, name in candidates if length == depth)
    return next(iter(owners)) if len(owners) == 1 else None


def _project_directories(root, index):
    """Recover declared project names, retaining conventional ownership where unambiguous."""
    result = {}
    for path in root.rglob('.project'):
        try:
            name = ElementTree.parse(path).getroot().findtext('name') or path.parent.name
        except (OSError, ElementTree.ParseError):
            continue
        if name in index.source_roots:
            result[name] = path.parent.resolve()
    for name, roots in index.source_roots.items():
        directory = root if name == '.' else root / name
        if name not in result and directory.is_dir() and all(Path(path).resolve().is_relative_to(directory) for path in roots):
            result[name] = directory
    return result
