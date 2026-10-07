"""Bind configured operation uses to originating Java implementations, not caller channels."""

import hashlib
from pathlib import Path
from xml.etree import ElementTree

from models.component_usage import ComponentInventory, ConfiguredComponentUse, ConfiguredComponentDefinition
from tools.component_inventory_tools.channel_mappings import load_channel_mappings
from tools.component_inventory_tools.definitions import discover_definitions
from tools.component_inventory_tools.identity import identify_java_source, stable_id
from tools.component_inventory_tools.xml_documents import tag_name
from tools.source_discovery_tools import discover_java_sources


def build_component_inventory(workspace_root, workspace_id=None, source_index=None):
    """Inventory all definitions and Java sources, retaining unresolved bindings explicitly.

    This first inventory slice does not infer arbitrary Java call graphs or method
    signatures. Missing framework sources remain configured uses with diagnostics.
    """
    workspace = Path(workspace_root).resolve()
    workspace_id = workspace_id or workspace.as_uri()
    index = source_index or discover_java_sources(str(workspace))
    inventory = ComponentInventory(workspace_id=workspace_id, diagnostics=list(index.issues))
    mappings, issues, scopes = load_channel_mappings(workspace)
    inventory.diagnostics.extend(issues)
    definitions, issues = discover_definitions(workspace)
    inventory.diagnostics.extend(issues)
    implementation_by_path = {}
    for fqcn, paths in index.classes.items():
        for value in paths:
            path = Path(value).resolve()
            project = index.class_projects.get(value)
            roots = [Path(root).resolve() for root in index.source_roots.get(project, []) if path.is_relative_to(Path(root).resolve())]
            if not roots:
                inventory.diagnostics.append("Source root is unavailable for " + value)
                continue
            implementation = identify_java_source(workspace, workspace_id, max(roots, key=lambda root: len(root.parts)), path, fqcn)
            implementation_by_path[str(path)] = implementation
            inventory.implementations.append(implementation)
    uses = {}
    configured = {}

    def resolve_class(fqcn, origin):
        if not fqcn:
            return None, "Java implementation mapping is unavailable"
        candidates = [str(Path(path).resolve()) for path in index.classes.get(fqcn, [])]
        own_projects = {project for project, roots in index.source_roots.items()
                        if any(origin.resolve().is_relative_to(Path(root).resolve()) for root in roots)}
        owned = [path for path in candidates if index.class_projects.get(path) in own_projects]
        if owned:
            candidates = owned
        if len(candidates) != 1:
            return None, ("Java source is missing: " if not candidates else "Java source is ambiguous: ") + fqcn
        implementation = implementation_by_path.get(candidates[0])
        return (implementation.implementation_id, None) if implementation else (None, "Java source root is unresolved: " + fqcn)

    def resolve_definition(kind, name, owner):
        candidates = [value for value in definitions if value["kind"] == kind and value["logical_id"] == name]
        local = [value for value in candidates if value["path"] == owner["path"]]
        if local:
            candidates = local
        elif owner["channel"]:
            same_channel = [value for value in candidates if value["channel"] == owner["channel"]]
            candidates = same_channel or [value for value in candidates if value["channel"] in scopes.get(owner["channel"], []) or value["channel"] is None]
        if len(candidates) != 1:
            return None, ("Missing" if not candidates else "Ambiguous") + " " + kind + " reference: " + name
        return candidates[0], None

    def identify_configuration(definition, node, kind, implementation_id=None, issue=None):
        path = definition["path"].relative_to(workspace).as_posix()
        selector = definition["selectors"][id(node)]
        identity = stable_id(workspace_id, path, selector)
        xml = ElementTree.tostring(node, encoding="unicode")
        record = ConfiguredComponentDefinition(definition_id=identity, component_kind=kind,
            channel=definition["channel"], source_path=path, selector=selector, logical_id=node.get("id"),
            configuration_hash=hashlib.sha256(xml.encode()).hexdigest(), configuration_xml=xml,
            implementation_id=implementation_id, resolution_issue=issue)
        configured.setdefault(identity, record)
        return configured[identity]

    def add_use(operation, definition, node, caller, kind=None, issue=None):
        tag = tag_name(node)
        channel = operation["channel"] or definition["channel"]
        mapping = mappings.get(channel, {}).get(tag)
        if tag == "opStep" and not node.get("implClass"):
            mapping = mappings.get(channel, {}).get(node.get("id")) or mapping
        explicit = node.get("implClass") or node.get("javaClass")
        fqcn = explicit or (mapping["fqcn"] if mapping else None)
        origin = definition["path"] if explicit or not mapping else workspace / mapping["source"]
        implementation_id = None
        # fmtDef is a configuration container; its formatter nodes bind Java implementations.
        if kind != "format":
            implementation_id, binding_issue = resolve_class(fqcn, origin)
            issue = issue or binding_issue
        group = mapping.get("group") if mapping else None
        kind = kind or ("opStep" if tag == "opStep" or group == "opSteps" else
                        "decorator" if mapping and ".decorator." in mapping["fqcn"].lower() else "formatter")
        configuration = identify_configuration(definition, node, kind, implementation_id, issue)
        xml = ElementTree.tostring(node, encoding="unicode")
        selector = definition["selectors"].get(id(node), definition["selector"])
        path = definition["path"].relative_to(workspace).as_posix()
        operation_key = stable_id(workspace_id, operation["path"].relative_to(workspace).as_posix(), operation["selector"])
        use = ConfiguredComponentUse(use_id=stable_id(operation_key, path, selector, caller), definition_id=configuration.definition_id, operation_key=operation_key,
            operation_id=operation["logical_id"], channel=operation["channel"], component_kind=kind,
            definition_path=path, definition_selector=selector, configuration_hash=hashlib.sha256(xml.encode()).hexdigest(),
            configuration_xml=xml, implementation_id=implementation_id,
            mapping_source=mapping["source"] if mapping and not explicit else None, referenced_by=caller, resolution_issue=issue)
        uses[use.use_id] = use
        if issue:
            inventory.diagnostics.append(operation["logical_id"] + ": " + path + selector + ": " + issue)

    def visit(operation, definition, caller, active):
        identity = (str(definition["path"]), definition["selector"])
        if identity in active:
            inventory.diagnostics.append(operation["logical_id"] + ": recursive configured reference at " + str(identity))
            return
        active = {*active, identity}
        root = definition["node"]
        if definition["kind"] in {"format", "context"}:
            add_use(operation, definition, root, caller, kind=definition["kind"])
        for node in root.iter():
            tag = tag_name(node)
            selector = definition["selectors"][id(node)]
            site = definition["path"].relative_to(workspace).as_posix() + selector
            references = []
            if tag == "refFormat" and node.get("refid"):
                references.append(("format", node.get("refid")))
            if node.get("refFmt"):
                references.append(("format", node.get("refFmt")))
            if node is root and definition["kind"] == "operation" and node.get("operationContext"):
                references.append(("context", node.get("operationContext")))
            if node is root and definition["kind"] == "context" and node.get("parent"):
                references.append(("context", node.get("parent")))
            for kind, name in references:
                target, error = resolve_definition(kind, name, definition)
                if error:
                    add_use(operation, definition, node, caller, kind=kind, issue=error)
                else:
                    visit(operation, target, caller + " -> " + site, active)
            if (node is root and definition["kind"] in {"format", "context"}) or tag in {"refFormat", "iniValue", "field"}:
                continue
            if tag == "opStep" or node.get("implClass") or node.get("javaClass") or tag in mappings.get(definition["channel"], {}):
                add_use(operation, definition, node, caller,
                        kind="operation" if node is root and definition["kind"] == "operation" else None)
            elif definition["kind"] == "format":
                add_use(operation, definition, node, caller)

    for definition in definitions:
        for node in definition["node"].iter():
            tag = tag_name(node)
            mapping = mappings.get(definition["channel"], {}).get(tag)
            if tag == "opStep" and not node.get("implClass"):
                mapping = mappings.get(definition["channel"], {}).get(node.get("id")) or mapping
            if node is definition["node"]:
                kind = definition["kind"]
            elif tag == "opStep":
                kind = "opStep"
            elif definition["kind"] == "format" and tag not in {"refFormat", "field"}:
                kind = "decorator" if mapping and ".decorator." in mapping["fqcn"].lower() else "formatter"
            else:
                continue
            explicit = node.get("implClass") or node.get("javaClass")
            origin = workspace / mapping["source"] if mapping and not explicit else definition["path"]
            implementation_id, issue = resolve_class(explicit or (mapping["fqcn"] if mapping else None), origin)
            if kind == "format":
                issue = None
            identify_configuration(definition, node, kind, implementation_id, issue)
    for operation in [value for value in definitions if value["kind"] == "operation"]:
        visit(operation, operation, "operation", set())
    inventory.uses = sorted(uses.values(), key=lambda use: use.use_id)
    inventory.definitions = sorted(configured.values(), key=lambda definition: definition.definition_id)
    from tools.component_inventory_tools.java_dependencies import build_java_dependency_graph
    inventory.java_dependencies = build_java_dependency_graph(workspace, index, inventory.implementations, inventory.uses)
    inventory.diagnostics.extend(issue.message for issue in inventory.java_dependencies.issues)
    inventory.diagnostics = sorted(set(inventory.diagnostics))
    return inventory
