"""Build a Java source index from Eclipse metadata or conventional layouts."""

import re
from pathlib import Path
from xml.etree import ElementTree

from models.java_source_index import JavaSourceIndex


def discover_java_sources(workspace_root: str) -> JavaSourceIndex:
    """Scan production roots, retaining metadata errors rather than hiding them.

    Sources outside the workspace and test source entries are excluded. The
    returned index is fresh on each call; persisted indexes are diagnostic snapshots.
    """
    workspace = Path(workspace_root).resolve()
    if not workspace.is_dir():
        raise ValueError("Java workspace must be an existing directory")
    index = JavaSourceIndex(workspace_root=str(workspace))
    metadata = set(workspace.rglob(".classpath")) | set(workspace.rglob(".project"))
    projects = {path.parent for path in metadata}
    known_names = {}
    for project in sorted(projects):
        name = project.name
        project_file = project / ".project"
        if project_file.exists():
            try:
                document = ElementTree.parse(project_file).getroot()
                name = document.findtext("name") or name
                index.project_references[name] = [node.text for node in document.findall("projects/project") if node.text]
            except (ElementTree.ParseError, OSError) as exc:
                index.issues.append(f"Invalid project metadata {project_file}: {exc}")
                continue
        if name in known_names:
            index.issues.append(f"Duplicate Eclipse project name: {name}")
            continue
        known_names[name] = project
        classpath = project / ".classpath"
        if not classpath.exists():
            _conventional_roots(index, workspace, project, name)
            continue
        try:
            entries = ElementTree.parse(classpath).getroot().findall("classpathentry")
        except (ElementTree.ParseError, OSError) as exc:
            index.issues.append(f"Invalid classpath metadata {classpath}: {exc}")
            continue
        for entry in entries:
            if entry.get("kind") != "src":
                continue
            value = entry.get("path", "")
            is_test = any(node.get("name") == "test" and node.get("value") == "true"
                          for node in entry.findall("attributes/attribute"))
            if is_test or _is_test_path(Path(value)):
                continue
            if value.startswith("/"):
                index.project_references.setdefault(name, []).append(value.lstrip("/"))
            else:
                _add_root(index, workspace, name, project / value)
    # Metadata owns its project's layout. Conventional discovery applies elsewhere.
    candidates = {workspace} | {path.parent for path in workspace.rglob("src") if path.is_dir()}
    for project in sorted(candidates):
        if any(project == owner or project.is_relative_to(owner) for owner in projects):
            continue
        _conventional_roots(index, workspace, project, str(project.relative_to(workspace)) or ".")
    if not index.source_roots and not metadata:
        _add_root(index, workspace, ".", workspace)
    for project, roots in index.source_roots.items():
        for root in roots:
            _index_classes(index, workspace, project, Path(root))
    for project, references in index.project_references.items():
        for reference in references:
            if reference not in index.source_roots:
                index.issues.append(f"Unresolved project reference from {project}: {reference}")
    return index


def _is_test_path(path: Path) -> bool:
    return any(part.lower() in {"test", "tests", "test-fixtures"} for part in path.parts)


def _conventional_roots(index, workspace, project, name):
    candidates = [project / "src/main/java", project / "src"]
    for candidate in candidates:
        if candidate.is_dir():
            _add_root(index, workspace, name, candidate)
            break


def _add_root(index, workspace, project, root):
    root = root.resolve()
    if not root.is_relative_to(workspace):
        index.issues.append(f"Source root outside workspace: {root}")
    elif not root.is_dir():
        index.issues.append(f"Missing source root: {root}")
    else:
        roots = index.source_roots.setdefault(project, [])
        if str(root) not in roots:
            roots.append(str(root))


def _index_classes(index, workspace, project, root):
    for path in sorted(root.rglob("*.java")):
        if _is_test_path(path.relative_to(root)) or not path.resolve().is_relative_to(workspace):
            continue
        try:
            source = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            index.issues.append(f"Cannot read Java source {path}: {exc}")
            continue
        source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
        match = re.search(r"\bpackage\s+([\w.]+)\s*;", source)
        package = match.group(1) if match else ""
        expected = Path(*package.split(".")) / path.name if package else Path(path.name)
        if path.relative_to(root) != expected:
            index.issues.append(f"Package does not match source root: {path}")
            continue
        fqcn = f"{package}.{path.stem}" if package else path.stem
        location = str(path.resolve())
        locations = index.classes.setdefault(fqcn, [])
        if location not in locations:
            locations.append(location)
        index.class_projects[location] = project
