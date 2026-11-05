"""Index original Composer XML definitions before any conversion-scope filtering."""

from xml.etree import ElementTree

from tools.component_inventory_tools.channel_mappings import channel_for_path
from tools.component_inventory_tools.xml_documents import read_xml, tag_name, walk_nodes


def discover_definitions(workspace, storage=None):
    """Keep every original definition occurrence; never overwrite by logical name."""
    if storage is not None:
        from tools.state_store_tools.inventory_records import DefinitionCatalog
        definitions = DefinitionCatalog(storage)
    else:
        definitions = []
    diagnostics = []
    kinds = {"CCDSEServerOperation": "operation", "fmtDef": "format", "context": "context", "opStep": "opStep"}
    for path in sorted(workspace.rglob("*.xml")):
        if not path.resolve().is_relative_to(workspace):
            diagnostics.append("XML source outside workspace: " + str(path))
            continue
        # Eclipse and application descriptors are not Composer source definitions.
        if path.name.lower() in {"pom.xml", "web.xml", "application.xml", "ejb-jar.xml", "beans.xml", "persistence.xml"}:
            continue
        try:
            root = read_xml(path)
            if storage is not None and storage.cache is not None:
                from tools.state_store_tools.workspace_analysis import content_hash
                current = content_hash(path)
                if str(path) in storage.cache.observed and storage.cache.observed[str(path)] != current:
                    raise ValueError('XML source changed during workspace analysis: ' + str(path))
                storage.cache.observed[str(path)] = current
        except (ValueError, OSError, ElementTree.ParseError) as exc:
            diagnostics.append(str(path.relative_to(workspace)) + ": " + str(exc))
            continue
        selectors = {id(node): selector for node, selector in walk_nodes(root)}
        for node in root.iter():
            kind = kinds.get(tag_name(node))
            if kind and node.get("id"):
                definitions.append(dict(kind=kind, logical_id=node.get("id"), node=node, path=path,
                                        channel=channel_for_path(path), selector=selectors[id(node)], selectors=selectors))
    return definitions, diagnostics
