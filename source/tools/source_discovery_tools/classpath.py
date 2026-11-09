"""Index configured JARs and Eclipse library entries without downloading artifacts."""

import os
import shutil
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from models.java_classpath_index import JavaClasspathIndex


def discover_java_classpath(workspace_root: str, jars: list[str] | None = None,
                            variables: dict[str, str] | None = None, *, visible_source_roots: list[str] | None = None,
                            containers: dict[str, list[str]] | None = None, project_containers=None, progress=None) -> JavaClasspathIndex:
    """Read explicit libraries and metadata; report unresolved containers and variables.

    The flat inventory describes availability; project_classpaths preserves the
    evidenced Eclipse build-path order separately from Maven dependency resolution.
    """
    workspace = Path(workspace_root).resolve()
    index = JavaClasspathIndex()
    libraries = {Path(path).resolve() for path in jars or []}
    from tools.source_discovery_tools.classpath_scope import mapped_classpath_roots, container_bindings
    containers = containers if containers is not None else container_bindings.get() or {}
    mapped_roots = mapped_classpath_roots(workspace)
    if mapped_roots is not None:
        visible_source_roots = sorted(set(mapped_roots) | set(visible_source_roots or []))
    origins = {}
    project_cache = {}
    resolved_containers = {}
    from models.project_classpath import ProjectClasspath
    from tools.source_discovery_tools.project_classpath import declaration, expand_projects
    source_index = None
    from models.classpath_issue import ClasspathIssue
    def issue(kind, reference, detail, project=None):
        index.issues.append(detail)
        index.issue_details.append(ClasspathIssue(project=project, reference=reference, kind=kind, detail=detail))
    for metadata in sorted(workspace.rglob(".classpath")):
        if visible_source_roots is not None and not any(Path(root).resolve().is_relative_to(metadata.parent.resolve()) for root in visible_source_roots):
            continue
        try:
            if progress:
                progress('Reading classpath: ' + str(metadata))
            from tools.composer_mapper_tools.mapped_scope import current_mapped, source_xml
            mapped = current_mapped(workspace)
            entries = (source_xml(mapped, metadata) if mapped is not None else ElementTree.parse(metadata).getroot()).findall("classpathentry")
        except (ElementTree.ParseError, OSError) as exc:
            issue('metadata', str(metadata), f"Invalid classpath {metadata}: {exc}", str(metadata.parent))
            continue
        from tools.source_discovery_tools.eclipse_metadata_snapshot import read_metadata
        try:
            project_file = metadata.parent / '.project'
            owner_document = (source_xml(mapped, project_file) if mapped is not None else ElementTree.parse(project_file).getroot()) if project_file.exists() else None
            read_metadata(metadata, workspace, index.metadata_fingerprints)
            read_metadata(project_file, workspace, index.metadata_fingerprints)
        except (ElementTree.ParseError, OSError, ValueError) as exc:
            issue('metadata', str(metadata), str(exc), str(metadata.parent))
            continue
        owner = (owner_document.findtext('name') if owner_document is not None else None) or metadata.parent.name
        if owner in index.project_classpaths:
            issue('metadata', str(metadata), 'Duplicate Eclipse project name: ' + owner, str(metadata.parent))
            continue
        owner_bindings = {**containers, **(project_containers or {}).get(owner, {})}
        view = ProjectClasspath(directory=str(metadata.parent))
        index.project_classpaths[owner] = view
        for position, entry in enumerate(entries):
            kind, value = entry.get("kind"), entry.get("path", "")
            exported = entry.get('exported') == 'true'
            if any(node.get("name") == "test" and node.get("value") == "true"
                   for node in entry.findall("attributes/attribute")):
                continue
            if kind == 'src' and not value.startswith('/'):
                from tools.source_discovery_tools.discovery import _is_test_path
                if _is_test_path(Path(value)):
                    continue
            if kind == "lib":
                from tools.source_discovery_tools.eclipse_library_paths import resolve_eclipse_library
                try:
                    path = resolve_eclipse_library(value, workspace, metadata.parent, project_cache=project_cache)
                except ValueError as exc:
                    issue('library', value, str(exc) + ' | project=' + str(metadata.parent), str(metadata.parent))
                    continue
                libraries.add(path.resolve())
                declaration(view, 'library', path.resolve(), value, exported, position)
                origins.setdefault(path.resolve(), []).append((str(metadata.parent), value))
            elif kind == "var":
                name, _, remainder = value.partition("/")
                base = (variables or {}).get(name)
                if base is None:
                    issue('variable', value, f"Unresolved Eclipse variable: {name} | project={metadata.parent} | reference={value}", str(metadata.parent))
                else:
                    path = (Path(base) / remainder).resolve()
                    libraries.add(path)
                    declaration(view, 'library', path, value, exported, position)
                    origins.setdefault(path, []).append((str(metadata.parent), value))
            elif kind == "con" and "JRE_CONTAINER" not in value:
                from tools.source_discovery_tools.eclipse_containers import container_libraries
                from tools.source_discovery_tools.eclipse_project_containers import project_container, junit_test_only, JUNIT_CONTAINER
                try:
                    key = (owner, value)
                    if key not in resolved_containers:
                        resolved_containers[key] = container_libraries(value, variables or {}, owner_bindings)
                    resolved = resolved_containers[key]
                    method = 'explicit_binding' if value in owner_bindings else 'configured_runtime'
                    if resolved is None:
                        def source_document(path):
                            if not path.exists():
                                return None
                            return source_xml(mapped, path) if mapped is not None else ElementTree.parse(path).getroot()
                        component = project_container(value, metadata.parent, workspace, index.metadata_fingerprints,
                                                      project_cache, source_document)
                        if component is not None:
                            resolved, references, method = component
                            index.project_references.update(references)
                            for target in references.get(owner, []):
                                # Deployment membership is source availability, not an exported Java build path.
                                declaration(view, 'module_project', target, value, exported, position, known=False)
                        elif value.startswith(JUNIT_CONTAINER):
                            if source_index is None:
                                from tools.source_discovery_tools import discover_java_sources
                                source_index = discover_java_sources(str(workspace))
                            if junit_test_only(metadata.parent, workspace, entries, source_index):
                                resolved, method = [], 'excluded_legacy_tests'
                    if resolved is not None:
                        record = dict(project=str(metadata.parent), reference=value, method=method,
                                      libraries=[str(path) for path in resolved], scope='test' if method == 'excluded_legacy_tests' else 'production')
                        index.container_resolutions.append(record)
                        if progress:
                            progress('Resolved container: ' + value + ' | project=' + str(metadata.parent) + ' | via=' + method)
                except (ValueError, OSError, ElementTree.ParseError) as exc:
                    issue('container', value, str(exc) + ' | project=' + str(metadata.parent) + ' | reference=' + value, str(metadata.parent))
                    continue
                if resolved is None:
                    issue('container', value, f"Unresolved Eclipse classpath container: {value} | project={metadata.parent}; configure its runtime or container JAR binding", str(metadata.parent))
                else:
                    for child, path in enumerate(resolved):
                        libraries.add(path.resolve())
                        declaration(view, 'library', path.resolve(), value, exported, position,
                                    child=child, known=value in owner_bindings)
                        origins.setdefault(path.resolve(), []).append((str(metadata.parent), value))
            elif kind == 'src':
                declaration(view, 'project' if value.startswith('/') else 'source',
                            value.lstrip('/') if value.startswith('/') else (metadata.parent / value).resolve(),
                            value, exported, position)
            elif kind == 'output':
                declaration(view, 'output', (metadata.parent / value).resolve(), value, exported, position)
            elif kind == 'con':
                declaration(view, 'platform', value, value, exported, position)
    expand_projects(index, jars or [])
    for library in sorted(libraries):
        if progress:
            progress('Indexing library: ' + str(library))
        before = len(index.issues)
        _index_archive(index, library, platform=False)
        for detail in index.issues[before:]:
            for project, reference in origins.get(library, [(None, str(library))]):
                index.issue_details.append(ClasspathIssue(project=project, reference=reference, kind='library', detail=detail))
    from runtime.java_toolchain import java_environment
    java_home = (java_environment() or os.environ).get("JAVA_HOME")
    executable = shutil.which("javac")
    jdk = Path(java_home) if java_home else Path(executable).resolve().parent.parent if executable else None
    if jdk and (jdk / "jmods").is_dir():
        for module in sorted((jdk / "jmods").glob("*.jmod")):
            _index_archive(index, module, platform=True)
    elif jdk and (jdk / "jre/lib/rt.jar").is_file():
        _index_archive(index, jdk / "jre/lib/rt.jar", platform=True)
    else:
        index.issues.append("JDK class inventory unavailable; configure JAVA_HOME")
    from tools.source_discovery_tools.eclipse_metadata_snapshot import publish_supplement
    from tools.source_discovery_tools.binary_resolution import classpath_for_project
    index.binary_resolutions = [choice for project in index.project_classpaths
        for choice in classpath_for_project(index, project).binary_resolutions]
    publish_supplement(workspace, index)
    return index


def _index_archive(index, archive, platform):
    if not archive.is_file():
        index.issues.append(f"Missing classpath library: {archive}")
        return
    try:
        with ZipFile(archive) as contents:
            for entry in contents.namelist():
                if not entry.endswith(".class") or entry.startswith("META-INF/"):
                    continue
                if platform:
                    entry = entry.removeprefix("classes/")
                if entry.endswith(("module-info.class", "package-info.class")):
                    continue
                name = entry[:-6].replace("/", ".").replace("$", ".")
                location = ("jdk:" if platform else "jar:") + str(archive)
                locations = index.classes.setdefault(name, [])
                if location not in locations:
                    locations.append(location)
        if not platform:
            index.libraries.append(str(archive))
    except (BadZipFile, OSError) as exc:
        index.issues.append(f"Invalid classpath archive {archive}: {exc}")
