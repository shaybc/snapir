"""Index configured JARs and Eclipse library entries without downloading artifacts."""

import os
import shutil
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from models.java_classpath_index import JavaClasspathIndex


def discover_java_classpath(workspace_root: str, jars: list[str] | None = None,
                            variables: dict[str, str] | None = None, *, visible_source_roots: list[str] | None = None,
                            containers: dict[str, list[str]] | None = None, progress=None) -> JavaClasspathIndex:
    """Read explicit libraries and metadata; report unresolved containers and variables.

    This index describes workspace availability, not Maven coordinates, transitive
    dependency resolution, or compiler classpath ordering.
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
        for entry in entries:
            kind, value = entry.get("kind"), entry.get("path", "")
            if any(node.get("name") == "test" and node.get("value") == "true"
                   for node in entry.findall("attributes/attribute")):
                continue
            if kind == "lib":
                from tools.source_discovery_tools.eclipse_library_paths import resolve_eclipse_library
                try:
                    path = resolve_eclipse_library(value, workspace, metadata.parent, project_cache=project_cache)
                except ValueError as exc:
                    issue('library', value, str(exc) + ' | project=' + str(metadata.parent), str(metadata.parent))
                    continue
                libraries.add(path.resolve())
                origins.setdefault(path.resolve(), []).append((str(metadata.parent), value))
            elif kind == "var":
                name, _, remainder = value.partition("/")
                base = (variables or {}).get(name)
                if base is None:
                    issue('variable', value, f"Unresolved Eclipse variable: {name} | project={metadata.parent} | reference={value}", str(metadata.parent))
                else:
                    path = (Path(base) / remainder).resolve()
                    libraries.add(path)
                    origins.setdefault(path, []).append((str(metadata.parent), value))
            elif kind == "con" and "JRE_CONTAINER" not in value:
                from tools.source_discovery_tools.eclipse_containers import container_libraries
                if value not in resolved_containers:
                    resolved_containers[value] = container_libraries(value, variables or {}, containers or {})
                resolved = resolved_containers[value]
                if resolved is None:
                    issue('container', value, f"Unresolved Eclipse classpath container: {value} | project={metadata.parent}; configure its runtime or container JAR binding", str(metadata.parent))
                else:
                    for path in resolved:
                        libraries.add(path.resolve())
                        origins.setdefault(path.resolve(), []).append((str(metadata.parent), value))
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
