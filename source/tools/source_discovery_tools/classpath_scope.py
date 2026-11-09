"""Select the project dependency closure represented by an indexed operation selection."""

from pathlib import Path
from contextvars import ContextVar

container_bindings = ContextVar('eclipse_container_bindings', default=None)


def with_component_projects(index, classpath):
    """Expose module source availability without scheduling packaged projects for conversion."""
    from copy import copy
    if classpath is None or not classpath.project_references:
        return index
    result = copy(index)
    result.project_references = {name: list(targets) for name, targets in index.project_references.items()}
    for name, targets in classpath.project_references.items():
        result.project_references[name] = sorted(set(result.project_references.get(name, [])) | set(targets))
    return result


def mapped_classpath_roots(workspace):
    """Return selected implementation and operation-owner roots, including declared project references."""
    from tools.composer_mapper_tools.mapped_scope import current_mapped
    mapped = current_mapped(workspace)
    if mapped is None:
        return None
    conn = mapped.analysis.conn
    projects = {row[0] for row in conn.execute('SELECT DISTINCT s.project FROM java_sources s JOIN selected_java j ON j.file=s.file')}
    directories = [(name, Path(mapped.location(path)).resolve()) for name, path in conn.execute('SELECT name,path FROM java_projects')]
    for (relative,) in conn.execute('SELECT n.source_relative_path FROM selected_contexts s JOIN operation_context_index o ON o.identity=s.identity JOIN notes n ON n.path=o.note'):
        source = mapped.workspace / relative
        owners = [(len(path.parts), name) for name, path in directories if source.is_relative_to(path)]
        if owners:
            depth = max(item[0] for item in owners)
            projects.update(name for length, name in owners if length == depth)
    pending = list(projects)
    while pending:
        for target in mapped.index.project_references.get(pending.pop(), []):
            if target not in projects:
                projects.add(target)
                pending.append(target)
    by_name = dict(directories)
    return [root for project in sorted(projects) for root in (
        mapped.index.source_roots.get(project) or ([str(by_name[project])] if project in by_name else []))]


def discover_conversion_classpath(source_root, jars=None, variables=None, *, profile=None, progress=None):
    """Use the same dependency scope at preparation and all later freshness boundaries."""
    roots = mapped_classpath_roots(source_root)
    if roots is None and profile is not None:
        from tools.source_discovery_tools import discover_java_sources
        from tools.conversion_tools.scoped_workflow.source_project import scoped_source_project
        index = discover_java_sources(source_root)
        channels = getattr(profile, 'channels', [])
        projects = {scoped_source_project(profile, channel, source_root=source_root, source_index=index) for channel in channels}
        projects.discard(None)
        explicit = getattr(profile, 'scoped_java_project', None)
        if explicit:
            projects.add(explicit)
        pending = list(projects)
        while pending:
            for target in index.project_references.get(pending.pop(), []):
                if target not in projects:
                    projects.add(target)
                    pending.append(target)
        if projects:
            roots = [root for project in sorted(projects) for root in index.source_roots.get(project, [])]
    from tools.source_discovery_tools.classpath import discover_java_classpath
    return discover_java_classpath(source_root, jars, variables, visible_source_roots=roots,
        containers=getattr(profile, 'eclipse_classpath_containers', {}) if profile is not None else None, progress=progress)
