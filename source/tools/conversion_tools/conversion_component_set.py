"""Resolve the component inputs shared by dependency closure and task scheduling."""

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from models.conversion_component import ConversionComponent
from models.conversion_models import ClosureBlockingIssue, ClosureStatus
from tools.state_store_tools.component_inventory import get_conversion_inventory


def resolve_conversion_components(conn, closure, workspace, source_index, external_rules=(), behavior_document=None, external_records=None):
    """Collect mapped implementations, recursive source dependencies, contexts, and formats."""
    components, issues, origins = {}, [], {}
    implementations, uses, graph = get_conversion_inventory(conn, closure.run_id, closure.operation_id, closure.channel)
    from tools.conversion_tools.external_dependency_resolver import external_dependency
    external_records = external_records if external_records is not None else []

    def external(name, origin):
        try:
            record = external_dependency(name, external_rules, behavior_document, origin,
                                         allow_framework=not source_index.classes.get(name))
            if record:
                if record not in external_records:
                    external_records.append(record)
                return True
        except (OSError, ValueError) as exc:
            issue(name, "External replacement contract is unavailable: " + str(exc))
            return True
        return False

    def issue(entity, detail):
        issues.append(ClosureBlockingIssue(kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
                                           entity_id=entity, detail=detail))

    def add(kind, identity, path=None, content=None, shared=False, origin="", expected_hash=None):
        try:
            path = Path(path).resolve() if path else None
            value = path.read_text(encoding="utf-8-sig") if path else content
            digest = hashlib.sha256(path.read_bytes() if path else value.encode()).hexdigest()
            if expected_hash and digest != expected_hash:
                raise ValueError("Source changed since intake; refresh intake before conversion")
            key = (kind, identity)
            if key in components and components[key].source_file != (str(path) if path else None):
                raise ValueError("Conflicting source identities")
            components[key] = ConversionComponent(kind=kind, logical_id=identity,
                source_file=str(path) if path else None, source_content=value, source_hash=digest,
                shared=shared, origin=origin)
        except (OSError, ValueError) as exc:
            issue(identity, f"{origin}: {exc}")

    for reference in closure.java_classes:
        if external(reference.fqcn, "Operation step"):
            continue
        add("ibm_java", reference.fqcn, reference.source_file, shared=reference.shared,
            origin=f"Operation step in {closure.channel}/{closure.operation_id}")
    pending = []
    from tools.component_inventory_tools.xml_documents import read_xml, walk_nodes
    xml_nodes = {}
    for use in uses:
        node = None
        try:
            node = ElementTree.fromstring(use["configuration_xml"])
            name = node.get("id") or node.tag.split("}")[-1]
        except ElementTree.ParseError:
            name = use["definition_selector"]
        if use["component_kind"] == "opStep" and name not in closure.included_opstep_ids:
            continue
        origin = f"{use['component_kind']} {name}: {use['definition_path']} {use['definition_selector']}"
        try:
            path = (Path(workspace) / use["definition_path"]).resolve()
            if path not in xml_nodes:
                xml_nodes[path] = {selector: ElementTree.tostring(node, encoding="unicode") for node, selector in walk_nodes(read_xml(path))}
            current = xml_nodes[path].get(use["definition_selector"])
            if current is None or hashlib.sha256(current.encode()).hexdigest() != use["configuration_hash"]:
                issue(name, origin + ": XML changed since intake; refresh intake before conversion")
                continue
        except (OSError, ValueError, ElementTree.ParseError) as exc:
            issue(name, origin + ": " + str(exc))
            continue
        problem = use.get("resolution_issue")
        if problem:
            implementation_name = problem.partition("Java source is missing: ")[2]
            if implementation_name and external(implementation_name, origin):
                continue
            if implementation_name and source_index.classes.get(implementation_name):
                problem = "Implementation source was not captured by intake; refresh intake: " + implementation_name
            # Older inventories recorded XML context containers as missing Java mappings.
            xml_context = use["component_kind"] == "context" and node is not None and not (node.get("implClass") or node.get("javaClass"))
            if not (xml_context and (problem == "Java implementation mapping is unavailable" or problem.lower().strip() == "missing context reference: nil")):
                issue(name, origin + ": " + problem)
        if use.get("implementation_id"):
            pending.append(use["implementation_id"])
            origins.setdefault(use["implementation_id"], origin)
    outgoing = {}
    for edge in graph.get("dependencies", []):
        outgoing.setdefault(edge["caller_implementation_id"], []).append(edge["target_implementation_id"])
    visited = set()
    external_ids = set()
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        item = implementations.get(key)
        if item is None:
            issue(key, "Implementation missing from the saved inventory")
            continue
        fqcn = ".".join(filter(None, [item.get("package_name"), item["class_name"]]))
        origin = origins.get(key, "Java dependency")
        if external(fqcn, origin):
            external_ids.add(key)
            continue
        add("ibm_java", fqcn, Path(workspace) / item["source_path"], origin=origin, expected_hash=item["source_hash"])
        for target in outgoing.get(key, []):
            origins.setdefault(target, origin + " -> dependency of " + fqcn)
            pending.append(target)
    for item in graph.get("issues", []):
        if item["implementation_id"] in visited and item["implementation_id"] not in external_ids:
            issue(item["implementation_id"], origins.get(item["implementation_id"], "Java implementation") + ": " + item["message"])
    # Legacy run inventories may lack use records; resolve their recorded tag mappings directly.
    if not uses:
        tags = set(closure.formats.formatter_tags)
        tags.update(tag for chain in closure.formats.decorator_chains.values() for tag in chain)
        for tag in sorted(tags):
            row = conn.execute("SELECT fqcn FROM tag_registry WHERE run_id=? AND tag_name=?", (closure.run_id, tag)).fetchone()
            paths = source_index.classes.get(row[0], []) if row else []
            if row and external(row[0], "Mapped tag " + tag):
                continue
            if len(paths) == 1:
                add("ibm_java", row[0], paths[0], origin="Mapped tag " + tag)
            else:
                issue(tag, "Mapped tag requires one available Java implementation source")
    if closure.context_id:
        add("xml_context", closure.context_id, content=json.dumps([field.model_dump(mode="json") for field in closure.context_fields]),
            origin="Operation context")
    for name in closure.formats.all_format_ids:
        row = conn.execute("SELECT source_path FROM source_artifacts WHERE run_id=? AND kind='format' AND logical_id=?",
                           (closure.run_id, name)).fetchone()
        if row:
            add("xml_fmtdef", name, row[0], shared=name in closure.shared_formats, origin="Referenced format")
        else:
            issue(name, "Referenced format source is unavailable")
    return list(components.values()), issues


def checked_conversion_units(closure):
    """Refuse unchecked or changed input sets instead of discovering new inputs during scheduling."""
    if not closure.get("conversion_components_checked"):
        raise ValueError("Dependency closure must be refreshed before scheduling conversion inputs")
    if closure.get("blocking_issues"):
        raise ValueError("Dependency closure has blocking issues; conversion inputs cannot be scheduled")
    units, sources = [], {}
    for data in closure.get("conversion_components", []):
        component = ConversionComponent.model_validate(data)
        value = Path(component.source_file).read_text(encoding="utf-8-sig") if component.source_file else component.source_content
        digest = hashlib.sha256(Path(component.source_file).read_bytes() if component.source_file else value.encode()).hexdigest()
        if digest != component.source_hash:
            raise ValueError(f"Conversion input changed after dependency checking: {component.logical_id}; refresh the closure")
        units.append((component.kind, component.logical_id, value, component.shared))
        if component.kind == "ibm_java":
            sources[component.logical_id] = component.source_file
    return units, sources
