"""Resolve declared module/web libraries and prove exclusion of legacy test containers."""

from pathlib import Path
from tools.source_discovery_tools.eclipse_component_metadata import component_metadata

MODULE_CONTAINER = 'org.eclipse.jst.j2ee.internal.module.container'
WEB_CONTAINER = 'org.eclipse.jst.j2ee.internal.web.container'
JUNIT_CONTAINER = 'org.eclipse.jdt.junit.JUNIT_CONTAINER/'


def project_container(reference, project, workspace, evidence, project_cache, source_document):
    """Return library paths, project references and resolution method, or None if unknown."""
    if reference not in (MODULE_CONTAINER, WEB_CONTAINER):
        return None
    resources, references = component_metadata(project, workspace, evidence)
    from tools.source_discovery_tools.eclipse_library_paths import _project_names
    if 'projects' not in project_cache:
        project_cache['projects'] = _project_names(Path(workspace))
    declared = project_cache['projects']
    for name in references:
        candidates = declared.get(name, [])
        if len(candidates) != 1:
            raise ValueError(('Missing' if not candidates else 'Ambiguous') + ' Eclipse module project: ' + name)
    libraries = []
    if reference == WEB_CONTAINER:
        folders = [(path, path / 'WEB-INF/lib') for path, destination in resources if destination.rstrip('/') == '']
        folders.extend((path, path) for path, destination in resources if destination.rstrip('/') == '/WEB-INF/lib')
        if not folders:
            raise ValueError('Web container has no declared web resource root: ' + str(project))
        for root, library_folder in folders:
            if not root.is_dir():
                raise ValueError('Missing Eclipse web resource root: ' + str(root))
            folder = library_folder.resolve()
            if not folder.is_relative_to(Path(project).resolve()):
                raise ValueError('Web library folder escapes project: ' + str(folder))
            if folder.is_dir():
                for path in sorted(folder.glob('*.jar')):
                    if not path.resolve().is_relative_to(Path(project).resolve()):
                        raise ValueError('Web library escapes project: ' + str(path))
                    libraries.append(path.resolve())
    owner = source_document(Path(project) / '.project')
    name = (owner.findtext('name') if owner is not None else None) or Path(project).name
    return libraries, {name: references}, 'component_metadata'


def junit_test_only(project, workspace, entries, source_index):
    """Exclude JUnit only with a test root and complete production evidence free of JUnit."""
    from tools.source_discovery_tools.discovery import _is_test_path
    source_entries = [entry for entry in entries if entry.get('kind') == 'src' and not entry.get('path', '').startswith('/')]
    if not any(_is_test_path(Path(entry.get('path', ''))) or any(
        node.get('name') == 'test' and node.get('value') == 'true' for node in entry.findall('attributes/attribute'))
        for entry in source_entries):
        return False
    from tools.composer_mapper_tools.mapped_scope import current_mapped
    mapped = current_mapped(workspace)
    if source_index.issues:
        return False
    owners = {name for name, roots in source_index.source_roots.items()
              if any(Path(root).resolve().is_relative_to(Path(project).resolve()) for root in roots)}
    if not owners:
        return False
    if mapped is not None:
        for owner in owners:
            for (file,) in mapped.analysis.conn.execute('SELECT file FROM java_sources WHERE project=?', (owner,)):
                if not mapped.analysis.conn.execute('SELECT 1 FROM java_facts WHERE file=? LIMIT 1', (file,)).fetchone():
                    return False
                facts = mapped.analysis.conn.execute('SELECT name,value FROM java_facts WHERE file=?', (file,))
                if any('junit' in ((name or '') + ' ' + (value or '')).lower() for name, value in facts):
                    return False
        return True
    for path, owner in source_index.class_projects.items():
        if owner in owners:
            from tools.java_analysis_tools.java_text import read_java_text
            if 'junit' in read_java_text(Path(path), strip_bom=True).lower():
                return False
    return True
