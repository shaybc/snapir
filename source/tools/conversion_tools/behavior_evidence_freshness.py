"""Verify configured XML evidence still matches the intake snapshot."""

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree
from tools.component_inventory_tools.xml_documents import read_xml, walk_nodes, tag_name


def verify_configuration_sources(conn, config, operation_id, channel):
    """Reject stale XML before conversion and later review/packaging reuse."""
    from tools.component_inventory_tools.channel_mappings import load_channel_mappings
    mappings, _, _ = load_channel_mappings(Path(config.source_root))
    implementations = {row[0]: json.loads(row[1]) for row in conn.execute(
        "SELECT implementation_id,record_json FROM source_implementations WHERE run_id=?", (config.run_id,))}
    documents, nodes = {}, {}
    rows = conn.execute("SELECT record_json FROM configured_component_uses WHERE run_id=? AND operation_id=? AND channel=?",
                        (config.run_id, operation_id, channel))
    for row in rows:
        use = json.loads(row[0])
        path = (Path(config.source_root) / use["definition_path"]).resolve()
        if path not in documents:
            nodes[path] = {selector: node for node, selector in walk_nodes(read_xml(path))}
            documents[path] = {selector: hashlib.sha256(ElementTree.tostring(node, encoding="unicode").encode()).hexdigest()
                               for selector, node in nodes[path].items()}
        if documents[path].get(use["definition_selector"]) != use["configuration_hash"]:
            raise ValueError("Configured XML changed since intake; refresh intake before conversion: " + str(path) + use["definition_selector"])
        if use.get("mapping_source"):
            node = nodes[path][use["definition_selector"]]
            channel_mapping = mappings.get(channel, {})
            mapping = channel_mapping.get(node.get("id")) if tag_name(node) == "opStep" else None
            mapping = mapping or channel_mapping.get(tag_name(node))
            implementation = implementations.get(use.get("implementation_id"))
            expected = implementation["package_name"] + "." + implementation["class_name"] if implementation else (
                use.get("resolution_issue") or "").partition("Java source is missing: ")[2]
            if mapping is None or mapping["source"] != use["mapping_source"] or (expected and mapping["fqcn"] != expected):
                raise ValueError("Composer tag mapping changed since intake; refresh intake: " + str(path) + use["definition_selector"])
