"""Prove selected Java origins using an explicit project/classpath profile and source revision."""

import hashlib
from collections import deque
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from models.conversion_models import ClosureStatus
from tools.conversion_tools.external_dependency_resolver import external_dependency
from tools.java_analysis_tools.java_source_reader import read_java_source
from tools.source_discovery_tools.dependencies import classify_java_imports
from tools.source_discovery_tools.resolver import resolve_indexed_source
from tools.conversion_tools.scoped_closure.platform_imports import verified_platform_wildcard


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
    rules = getattr(profile, 'external_dependencies', ()) if profile else ()
    document = getattr(profile, 'composer_behavior_document', None) if profile else None
    contextual = {entry['fqcn']: entry for entry in access.java_resolution(context)}
    dependencies_allowed = set(required) if captured_dependencies else set()
    while pending:
        fqcn = pending.popleft()
        if fqcn in visited:
            continue
        visited.add(fqcn)
        try:
            candidates = contextual.get(fqcn, {}).get('candidates', [])
            record = external_dependency(fqcn, rules, document, 'Qualified operation ' + context.operation_identity,
                                         allow_framework=not candidates and not (
                                             source_index and source_index.classes.get(fqcn)))
            if record and record['treatment'] == 'replace':
                external.append(record)
                origins.append(dict(fqcn=fqcn, status='explicit_replacement', evidence=record))
                continue
            if classpath_index is None or classpath_index.issues:
                raise ValueError('An explicit resolved classpath profile is required: ' + fqcn)
            locations = classpath_index.classes.get(fqcn, [])
            if record and record['treatment'] == 'retain':
                if len(locations) != 1 or not locations[0].startswith('jar:'):
                    raise ValueError('Retained class requires one proven library origin: ' + fqcn)
                digest = _binary_digest(locations[0], fqcn)
                external.append(record)
                origins.append(dict(fqcn=fqcn, status='verified_retention', location=locations[0],
                                    source_hash=digest, evidence=record))
                continue
            if not candidates and len(locations) == 1 and locations[0].startswith('jdk:'):
                digest = _binary_digest(locations[0], fqcn)
                origins.append(dict(fqcn=fqcn, status='verified_platform', location=locations[0], source_hash=digest))
                continue
            if java_project is None or source_index is None or java_project not in source_index.source_roots:
                raise ValueError('An explicit production source-project profile is required: ' + fqcn)
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
            read_java_source(str(path), expected_hash=digest)  # Bind the guarded read to the proved revision.
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
                elif kind in ('missing', 'ambiguous', 'needs_review'):
                    issue(fqcn, 'Unresolved Java dependency: ' + imported + ' (' + kind + ')',
                          ClosureStatus.BLOCKED_MISSING_IMPL_CLASS)
        except (ValueError, OSError, BadZipFile) as exc:
            issue(fqcn, str(exc), ClosureStatus.BLOCKED_MISSING_IMPL_CLASS)
            origins.append(dict(fqcn=fqcn, status='unresolved_classpath', detail=str(exc)))
    return origins, external
