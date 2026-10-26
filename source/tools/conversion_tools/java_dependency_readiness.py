"""Check Java references across the complete conversion component set."""

import constants
import hashlib
from pathlib import Path
from xml.etree import ElementTree

from models.conversion_component import ConversionComponent
from models.conversion_models import ClosureBlockingIssue, ClosureStatus
from tools.java_analysis_tools.source_dependencies.parser import parse_source_references
from tools.java_analysis_tools.source_dependencies.resolution import resolve_reference


def _binary_names(name, document):
    """Expand an unresolved type using explicit imports, its package, and wildcard imports."""
    head, _, tail = name.partition(".")
    if tail and head[:1].islower():
        return [name]
    explicit = [node.get("name") + ("." + tail if tail else "") for node in document.findall("import")
                if node.get("static") != "true" and not node.get("name").endswith(".*")
                and node.get("name").rsplit(".", 1)[-1] == head]
    if explicit:
        return explicit
    package = document.get("package", "")
    names = [name, (package + "." if package else "") + name, "java.lang." + name]
    names.extend(node.get("name")[:-1] + name for node in document.findall("import")
                 if node.get("static") != "true" and node.get("name").endswith(".*"))
    return names


def check_java_dependencies(components, source_index, classpath, expected_hashes=None, external_rules=(), behavior_document=None, external_records=None):
    """Follow source dependencies recursively and report unresolved type references with origins."""
    issues = []
    expected_hashes = expected_hashes or {}
    from tools.conversion_tools.external_dependency_resolver import external_dependency
    external_records = external_records if external_records is not None else []
    by_path = {str(Path(item.source_file).resolve()): item for item in components if item.kind == "ibm_java"}
    pending = set(by_path)
    visited = set()
    while pending:
        batch = sorted(pending - visited)
        if not batch:
            break
        visited.update(batch)
        analysis = parse_source_references(batch)
        for document in analysis.findall("source"):
            path = str(Path(document.get("path")).resolve())
            owner = by_path[path]
            ignored = {node.get("name") for tag in ("local_type", "type_parameter") for node in document.findall(tag)}
            references = list(document.findall("reference"))
            for imported in document.findall("import"):
                name = imported.get("name")
                if not name.endswith(".*"):
                    if imported.get("static") == "true":
                        name = name.rsplit(".", 1)[0]
                    references.append(ElementTree.Element("reference", name=name, kind="type"))
            for reference in references:
                name, kind = reference.get("name"), reference.get("kind")
                if kind == "type" and name not in ignored:
                    try:
                        records = [record for candidate in _binary_names(name, document)
                                   if (record := external_dependency(candidate, external_rules, behavior_document, owner.origin + " -> " + owner.logical_id + " requires " + name))]
                    except (OSError, ValueError) as exc:
                        _issue(issues, name, owner, "External replacement contract is unavailable: " + str(exc))
                        continue
                    if records:
                        for record in records:
                            if record not in external_records:
                                external_records.append(record)
                        continue
                targets, error = resolve_reference(reference, document, source_index, path)
                if error:
                    _issue(issues, name, owner, error)
                    continue
                if targets:
                    for target in targets:
                        target = str(Path(target).resolve())
                        fqcn = next((fqcn for fqcn, paths in source_index.classes.items() if target in paths), name)
                        try:
                            record = external_dependency(fqcn, external_rules, behavior_document, owner.origin + " -> " + owner.logical_id + " requires " + name)
                        except (OSError, ValueError) as exc:
                            _issue(issues, name, owner, "External replacement contract is unavailable: " + str(exc))
                            continue
                        if record:
                            if record not in external_records:
                                external_records.append(record)
                            continue
                        if target not in by_path:
                            if expected_hashes and target not in expected_hashes:
                                _issue(issues, name, owner, "Dependency source was not captured by intake; refresh intake")
                                continue
                            from tools.java_analysis_tools.java_source_reader import read_java_source
                            content = read_java_source(target)
                            digest = hashlib.sha256(Path(target).read_bytes()).hexdigest()
                            if target in expected_hashes and digest != expected_hashes[target]:
                                _issue(issues, name, owner, "Dependency source changed since intake; refresh intake")
                                continue
                            by_path[target] = ConversionComponent(kind="ibm_java", logical_id=fqcn,
                                source_file=target, source_content=content, source_hash=digest,
                                origin=owner.origin + " -> " + owner.logical_id + " requires " + name)
                        pending.add(target)
                    continue
                if kind != "type" or name in ignored:
                    continue
                matches = set()
                for candidate in _binary_names(name, document):
                    variants = [candidate]
                    while "." in candidate:
                        candidate = candidate.rsplit(".", 1)[0] + "$" + candidate.rsplit(".", 1)[1]
                        variants.append(candidate)
                    for candidate in variants:
                        matches.update(classpath.classes.get(candidate, []))
                # Classify framework boundaries only after source and binary resolution.
                # A JDK match must not become an invented same-package Composer type.
                if len(matches) <= 1 and (not matches or any(classpath.classes.get(candidate) for candidate in _binary_names(name, document)
                    if candidate.startswith(tuple(package + "." for package in constants.COMPOSER_FRAMEWORK_PACKAGES)))):
                    records = [record for candidate in _binary_names(name, document)
                               if (record := external_dependency(candidate, external_rules, behavior_document,
                                   owner.origin + " -> " + owner.logical_id + " requires " + name, allow_framework=True))]
                    if records:
                        for record in records:
                            if record not in external_records:
                                external_records.append(record)
                        continue
                if not matches:
                    _issue(issues, name, owner, "Type has no source, JDK, or configured classpath definition; supply its source or replacement")
                elif len(matches) > 1:
                    _issue(issues, name, owner, "Type resolves to multiple classpath definitions; select one dependency")
        for error in analysis.findall("issue"):
            path = str(Path(error.get("path")).resolve()) if error.get("path") else None
            owner = by_path.get(path)
            if owner:
                _issue(issues, owner.logical_id, owner, "Java syntax: " + error.get("message"))
    java = list(by_path.values())
    return [item for item in components if item.kind != "ibm_java"] + java, issues


def _issue(issues, name, owner, detail):
    """Tie an unresolved reference back to the XML use and its implementation source."""
    issues.append(ClosureBlockingIssue(kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
        entity_id=name, detail=f"{owner.logical_id} requires {name}: {detail}. Source: {owner.source_file}. Origin: {owner.origin}"))
