"""Reuse the complete Java syntax dependency gate with qualified intake hash coverage."""

from pathlib import Path

from models.conversion_component import ConversionComponent
from tools.conversion_tools.java_dependency_readiness import check_java_dependencies
from tools.conversion_tools.scoped_closure.java_origins import resolve_java_origins
from tools.java_analysis_tools.java_source_reader import read_java_source


def check_scoped_java_dependencies(access, context, sources, origins, external, source_index,
                                   classpath_index, java_project, profile, issue):
    """Check actual type sites, requiring captured revisions and declared project visibility."""
    verified = [origin for origin in origins if origin.get('status') == 'verified_source']
    if not verified:
        return
    allowed, pending = set(), [java_project]
    while pending:
        project = pending.pop()
        if project in allowed:
            continue
        allowed.add(project)
        pending.extend(source_index.project_references.get(project, []))
    # The legacy syntax resolver must not see classes outside the explicit profile.
    scoped_index = source_index.model_copy(update={
        'classes': {name: [path for path in paths if source_index.class_projects[path] in allowed]
                    for name, paths in source_index.classes.items()
                    if any(source_index.class_projects[path] in allowed for path in paths)}})
    hashes = {}
    for relative, digest in access.captured_java_revisions(context):
        path = (sources.root / relative).resolve()
        if not Path(relative).is_absolute() and path.is_relative_to(sources.root):
            hashes[str(path)] = digest
    components = [ConversionComponent(kind='ibm_java', logical_id=origin['fqcn'],
        source_file=origin['source_file'], source_hash=origin['source_hash'],
        source_content=read_java_source(origin['source_file'], expected_hash=origin['source_hash']), origin=context.operation_identity)
        for origin in verified]
    rules = getattr(profile, 'external_dependencies', ()) if profile else ()
    document = getattr(profile, 'composer_behavior_document', None) if profile else None
    # A non-empty map also blocks unrecorded helpers when the intake had no other Java candidates.
    hashes.update({item.source_file: item.source_hash for item in components})
    checked, problems = check_java_dependencies(components, scoped_index, classpath_index, hashes,
                                               rules, document, external)
    for problem in problems:
        issue(problem.entity_id, problem.detail, problem.kind)
    existing = {origin['fqcn'] for origin in origins}
    names = {component.logical_id for component in checked if component.logical_id not in existing}
    if names:
        additional, records = resolve_java_origins(access, context, sources, names, scoped_index,
                                                  classpath_index, java_project, profile, issue, captured_dependencies=True)
        origins.extend(additional)
        external.extend(record for record in records if record not in external)
