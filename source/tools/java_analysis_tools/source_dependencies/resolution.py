"""Resolve syntax references to original classes without merging different source copies."""

from pathlib import Path
import re


def resolve_reference(reference, document, source_index, source_path):
    """Return eligible source paths and an ambiguity note, or no source dependency.

    Imports establish names, not usage. Binary/JDK types stay outside this graph.
    Attribution beyond syntactic source identity remains the compiler's responsibility.
    """
    name = reference.get("name")
    kind = reference.get("kind")
    imports = [(node.get("name"), node.get("static") == "true") for node in document.findall("import")]
    variables = {node.get("name") for node in document.findall("variable")}
    parameters = {node.get("name") for node in document.findall("type_parameter")}
    local_types = {node.get("name") for node in document.findall("local_type")}
    if kind == "qualifier" and name.split(".")[0] in variables | {"this", "super"}:
        return [], None
    if kind in {"static_member", "static_field"}:
        if name in variables | {"this", "super"} or kind == "static_member" and name in {node.get("name") for node in document.findall("method")}:
            return [], None
        names = [imported.rsplit(".", 1)[0] for imported, static in imports
                 if static and (imported.endswith("." + name) or imported.endswith(".*"))]
    else:
        if name in parameters | local_types:
            return [], None
        if not all(re.fullmatch(r"(?:[^\W\d]|[$_])[\w$]*", part) for part in name.split(".")):
            return [], None
        head, _, tail = name.partition(".")
        explicit = [imported + ("." + tail if tail else "") for imported, static in imports
                    if not static and not imported.endswith(".*") and imported.rsplit(".", 1)[-1] == head]
        if explicit:
            names = explicit
        else:
            package = document.get("package", "")
            same_package = (package + "." if package else "") + name
            if name in source_index.classes or same_package in source_index.classes:
                names = [name] if name in source_index.classes else [same_package]
            else:
                names = [name, same_package]
                names.extend(imported[:-1] + name for imported, static in imports if not static and imported.endswith(".*"))
    candidates = set()
    for fqcn in names:
        # Resolve an enclosing source file for a nested type or static qualifier.
        current = fqcn
        while current:
            if current in source_index.classes:
                candidates.update(source_index.classes[current])
                break
            current = current.rsplit(".", 1)[0] if "." in current else ""
    owner = source_index.class_projects.get(str(Path(source_path).resolve()))
    own = {path for path in candidates if source_index.class_projects.get(path) == owner}
    if own:
        candidates = own
    elif owner in source_index.project_references:
        allowed = {owner}
        pending = [owner]
        while pending:
            for project in source_index.project_references.get(pending.pop(), []):
                if project not in allowed:
                    allowed.add(project)
                    pending.append(project)
        eligible = {path for path in candidates if source_index.class_projects.get(path) in allowed}
        if candidates and not eligible:
            return [], "Java source reference is outside declared project visibility: " + name
        candidates = eligible
    if len(candidates) > 1:
        return [], "Ambiguous Java source reference: " + name
    return sorted(candidates), None
