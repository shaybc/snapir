"""Resolve Eclipse workspace library names without interpreting them as drive-root paths."""

from pathlib import Path, PureWindowsPath
from xml.etree import ElementTree


def resolve_eclipse_library(value, workspace, project, *, project_cache=None):
    """Preserve explicit filesystem paths; resolve Eclipse-rooted names by project identity."""
    workspace, project = Path(workspace).resolve(), Path(project).resolve()
    windows = PureWindowsPath(value)
    if windows.drive:
        return Path(value)
    normalized = value.replace('\\', '/')
    if not normalized.startswith('/'):
        return project / normalized
    parts = normalized.lstrip('/').split('/')
    # POSIX absolute filesystem paths remain supported when they are not project references.
    cache = project_cache if project_cache is not None else {}
    if 'projects' not in cache:
        cache['projects'] = _project_names(workspace)
    candidates = list(cache['projects'].get(parts[0], []))
    conventional = workspace / parts[0]
    if conventional.is_dir() and not (conventional / '.project').exists():
        candidates.append(conventional)
    candidates = set(candidates)
    if len(candidates) > 1:
        raise ValueError('Ambiguous Eclipse workspace project: ' + parts[0])
    if candidates:
        base = next(iter(candidates))
        result = base.joinpath(*parts[1:]).resolve()
        if not result.is_relative_to(base):
            raise ValueError('Eclipse library reference escapes its project: ' + value)
        return result
    if Path(value).is_absolute():
        return Path(value)
    return workspace.joinpath(*parts)


def _project_names(workspace):
    from tools.composer_mapper_tools.mapped_scope import current_mapped, source_xml
    mapped = current_mapped(workspace)
    metadata_files = (Path(mapped.location(row[0])) for row in mapped.analysis.conn.execute(
        "SELECT path FROM files WHERE lower(relative_path) LIKE '%.project'")) if mapped is not None else workspace.rglob('.project')
    result = {}
    for metadata in metadata_files:
        try:
            root = source_xml(mapped, metadata) if mapped is not None else ElementTree.parse(metadata).getroot()
            result.setdefault(root.findtext('name') or metadata.parent.name, []).append(metadata.parent.resolve())
        except (OSError, ElementTree.ParseError):
            continue
    return result
