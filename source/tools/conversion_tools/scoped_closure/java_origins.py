"""Prove selected Java origins using an explicit project/classpath profile and source revision."""

import hashlib
from collections import deque
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from models.conversion_models import ClosureStatus
from tools.conversion_tools.external_dependency_resolver import external_dependency
from tools.java_analysis_tools.java_text import read_java_text
from tools.source_discovery_tools.dependencies import classify_java_imports
from tools.source_discovery_tools.resolver import resolve_indexed_source
from tools.conversion_tools.scoped_closure.platform_imports import verified_platform_wildcard
from tools.conversion_tools.dependency_treatment import dependency_record


def _binary_digest(location, fqcn):
    """Verify the named class remains in the selected archive, then hash its bytes."""
    archive = Path(location[4:])
    with ZipFile(archive) as contents:
        names = [name.removeprefix('classes/') if location.startswith('jdk:') else name
                 for name in contents.namelist() if name.endswith('.class') and not name.startswith('META-INF/')]
        if not any(name[:-6].replace('/', '.').replace('$', '.') == fqcn.replace('$', '.') for name in names):
            raise ValueError('Selected binary origin does not contain ' + fqcn)
    with archive.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def resolve_java_origins(access, context, sources, required, source_index, classpath_index,
                         java_project, profile, issue, *, captured_dependencies=False):
    """Resolve actual requirements; a unique Mapper candidate does not establish classpath proof.

    The project and classpath index are explicit analysis inputs. No filesystem or
    candidate ordering is used to decide between competing source/binary origins.
    """
    origins, external, visited = [], [], set()
    pending = deque(sorted(required))
    roots = set(required)
    rules = getattr(profile, 'external_dependencies', ()) if profile else ()
    document = getattr(profile, 'composer_behavior_document', None) if profile else None
    contextual = {entry['fqcn']: entry for entry in access.java_resolution(context)}
    if classpath_index is not None and classpath_index.issues:
        details = {item.detail: item for item in classpath_index.issue_details}
        reasons = []
        for message in dict.fromkeys(classpath_index.issues):
            detail = details.get(message)
            if detail and detail.project and 'project=' not in message:
                message += ' | project=' + detail.project + ' | reference=' + detail.reference
            reasons.append(message)
        issue('classpath', 'Required project classpath is incomplete: ' + '; '.join(reasons),
              ClosureStatus.BLOCKED_MISSING_IMPL_CLASS)
        return origins, external
    dependencies_allowed = set(required) if captured_dependencies else set()
    while pending:
        fqcn = pending.popleft()
        if fqcn in visited:
            continue
        visited.add(fqcn)
        try:
            candidates = contextual.get(fqcn, {}).get('candidates', [])
            from tools.source_discovery_tools.binary_resolution import classpath_for_project
            source_paths = source_index.classes.get(fqcn, []) if source_index else []
            owner = source_index.class_projects.get(source_paths[0], java_project) if len(source_paths) == 1 else java_project
            resolved_classpath = classpath_for_project(classpath_index, owner)
            record = dependency_record(fqcn, rules, profile, 'Qualified operation ' + context.operation_identity,
                                       resolved_classpath, source_exists=bool(source_index and source_index.classes.get(fqcn)),
                                       required=fqcn in roots and not captured_dependencies)
            if record and record['treatment'] == 'candidate':
                external.append(record)
                origins.append(dict(fqcn=fqcn, status='evidence_dependency', evidence=record))
                continue
            if record and record['treatment'] == 'replace':
                external.append(record)
                origins.append(dict(fqcn=fqcn, status='explicit_replacement', evidence=record))
                continue
            if classpath_index is None or classpath_index.issues:
                raise ValueError('An explicit resolved classpath profile is required: ' + fqcn)
            locations = resolved_classpath.classes.get(fqcn, [])
            if record and record['treatment'] == 'retain':
                if len(locations) != 1 or not locations[0].startswith('jar:'):
                    raise ValueError('Retained class requires one proven library origin: ' + fqcn)
                digest = _binary_digest(locations[0], fqcn)
                external.append(record)
                origins.append(dict(fqcn=fqcn, status='verified_retention', location=locations[0],
                                    source_hash=digest, evidence=record,
                                    binary_resolution=next((item for item in resolved_classpath.binary_resolutions
                                        if item['class_name'] == fqcn), None)))
                continue
            if not candidates and len(locations) == 1 and locations[0].startswith('jdk:'):
                digest = _binary_digest(locations[0], fqcn)
                origins.append(dict(fqcn=fqcn, status='verified_platform', location=locations[0], source_hash=digest))
                continue
            if java_project is None or source_index is None or java_project not in source_index.source_roots:
                raise ValueError('Production source project is missing or ambiguous in workspace metadata: ' + fqcn)
            projects, queue = set(), [java_project]
            while queue:
                project = queue.pop()
                if project in projects:
                    continue
                projects.add(project)
                if project not in source_index.source_roots:
                    raise ValueError('Unresolved project dependency: ' + project)
                queue.extend(source_index.project_references.get(project, []))
            source = resolve_indexed_source(source_index, fqcn, project=java_project)
            if not source:
                raise ValueError('Implementation lacks verified production source or explicit retention: ' + fqcn)
            if locations:
                raise ValueError('Competing source/binary classpath origins require an explicit selection: ' + fqcn)
            relative = Path(source).resolve().relative_to(sources.root).as_posix()
            reference = (access.captured_java_dependency(context, fqcn, relative)
                         if not candidates
                         else access.java_candidate(context, fqcn, relative))
            path = sources.path(relative)
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != reference.evidence['source_hash']:
                raise ValueError('Java source revision differs from intake: ' + relative)
            read_java_text(str(path), expected_hash=digest)  # Bind the analysis read to the proved revision.
            dependencies = classify_java_imports(str(path), source_index, classpath_index)
            for dependency in dependencies:
                if dependency['kind'] == 'needs_review' and verified_platform_wildcard(
                        dependency['import_name'], source_index, classpath_index):
                    dependency.update(kind='platform_wildcard', reason='Indexed JDK package; actual type sites require syntax validation')
            origins.append(dict(fqcn=fqcn, status='verified_source', definition_id=reference.definition_id,
                source_file=str(path), source_hash=digest, source_project=source_index.class_projects[str(path)],
                profile_project=java_project, dependencies=dependencies,
                return_codes=reference.evidence.get('parsed', {}).get('return_codes', {})))
            for dependency in dependencies:
                kind, imported = dependency['kind'], dependency['import_name']
                if kind in ('source', 'replacement_required', 'library'):
                    # Resolve static imports to their evidenced enclosing class, not a method name.
                    names = [name for name in source_index.classes if imported == name or imported.startswith(name + '.')]
                    dependency_name = max(names, key=len) if names else imported
                    dependencies_allowed.add(dependency_name)
                    pending.append(dependency_name)
                elif kind in ('missing', 'ambiguous'):
                    pending.append(imported)
                elif kind == 'needs_review':
                    issue(fqcn, 'Unresolved Java dependency: ' + imported + ' (' + kind + ')',
                          ClosureStatus.BLOCKED_MISSING_IMPL_CLASS)
        except (ValueError, OSError, BadZipFile) as exc:
            issue(fqcn, str(exc), ClosureStatus.BLOCKED_MISSING_IMPL_CLASS)
            origins.append(dict(fqcn=fqcn, status='unresolved_classpath', detail=str(exc)))
    return origins, external
