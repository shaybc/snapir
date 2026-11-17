"""Discover FormatElement descendants using the existing source/JAR symbol resolver."""
import hashlib
import logging
from pathlib import Path
from types import SimpleNamespace


def format_candidates(root, catalog, profile=None, classpath=None):
    """Resolve ancestry only; never execute code or select a containing format's methods."""
    from models.pipeline_configuration import PipelineConfiguration
    from tools.source_discovery_tools.classpath_scope import discover_conversion_classpath
    from tools.behavior_verification.boundary_classpath import project_context
    from tools.behavior_verification.framework_jars import framework_libraries
    from tools.behavior_verification.java_tool import analyze_entries

    profile = profile or PipelineConfiguration()
    index, documents = catalog
    if not index.classes:
        return []
    if classpath is None:
        classpath = discover_conversion_classpath(root, profile.classpath_jars,
            profile.eclipse_classpath_variables, profile=profile)
    sources, origins = [], []
    names_by_path = {}
    for name, paths in index.classes.items():
        for path in paths:
            names_by_path.setdefault(path, []).append(name)
    for path in sorted(documents):
        content = Path(path).read_text(encoding='utf-8-sig')
        identity = hashlib.sha256(path.encode()).hexdigest()
        sources.append(dict(identity=identity, content=content,
                            content_hash=hashlib.sha256(content.encode()).hexdigest()))
        for name in names_by_path.get(path, []):
            origins.append(dict(definition_id=identity, fqcn=name, source_file=path,
                source_project=index.class_projects[path], status='verified_source'))
    names = sorted(index.classes)
    context = project_context(dict(sources=sources), SimpleNamespace(implementation_class=names[0]), origins, classpath)
    boundaries = [SimpleNamespace(unit_id=name, implementation_class=name, method_name='',
        return_contract='', kind='response_format', parameter_contract=[], setup_class_roots=[], setup_bindings=[])
        for name in names]
    scope = dict(sources=sources, boundaries=boundaries, classpath=context,
                 framework_libraries=framework_libraries(profile.framework_jars))
    analysis, _ = analyze_entries({'formats': scope}, collect_checklists=False, candidate_only=True)
    found = []
    for entry in analysis.findall('entry'):
        candidate = entry.find('format-candidate')
        if candidate is not None and candidate.get('identified') == 'true':
            found.append(entry.get('id'))
        for issue in entry.findall('issue'):
            logging.getLogger(__name__).warning('Format ancestry unresolved for %s: %s', entry.get('id'), issue.get('message'))
    return sorted(found)
