"""Summarize distinct inventoried dependencies within each proposed batch."""

import json
import xml.etree.ElementTree as ET


def load_composition(conn, run_id):
    """Load per-operation definition and Java-class identities for presentation."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"configured_component_uses", "configured_component_definitions", "source_implementations"}.issubset(tables):
        return None
    definitions = {}
    for row in conn.execute("SELECT record_json FROM configured_component_definitions WHERE run_id=?", (run_id,)):
        item = json.loads(row[0])
        name = item.get("logical_id")
        if not name:
            try:
                name = ET.fromstring(item.get("configuration_xml", "")).tag
            except ET.ParseError:
                name = "Unnamed definition"
        definitions[item["definition_id"]] = name + " (" + item.get("source_path", "source unavailable") + "; " + item.get("selector", "location unavailable") + ")"
    implementations = {}
    for row in conn.execute("SELECT record_json FROM source_implementations WHERE run_id=?", (run_id,)):
        item = json.loads(row[0])
        implementations[item["implementation_id"]] = ".".join(filter(None, [item.get("package_name"), item.get("class_name")])) or item.get("source_path", "Unnamed Java class")
    result = {}
    for row in conn.execute("SELECT record_json FROM configured_component_uses WHERE run_id=?", (run_id,)):
        use = json.loads(row[0])
        groups = result.setdefault((use.get("channel"), use["operation_id"]), {})
        kind = use["component_kind"]
        if kind != "operation":
            groups.setdefault(kind, {})[use["definition_id"]] = definitions.get(use["definition_id"], "Definition details unavailable")
        if use.get("implementation_id"):
            key = use["implementation_id"]
            groups.setdefault("Java implementation classes", {})[key] = implementations.get(key, "Class details unavailable")
    if "java_dependency_uses" in tables:
        for row in conn.execute("SELECT record_json FROM java_dependency_uses WHERE run_id=?", (run_id,)):
            use = json.loads(row[0])
            groups = result.setdefault((use.get("channel"), use["operation_id"]), {})
            key = use["implementation_id"]
            groups.setdefault("Additional Java dependencies", {})[key] = implementations.get(key, "Class details unavailable")
    for groups in result.values():
        for key in groups.get("Java implementation classes", {}):
            groups.get("Additional Java dependencies", {}).pop(key, None)
    return result


def composition_lines(packets, inventory, include_details=True, collapsible=False):
    """Render deduplicated batch totals and named per-operation dependencies."""
    if inventory is None:
        return ["  Component inventory unavailable; review the legacy source for batch composition."]
    labels = {"opStep": "Operation step definitions", "format": "Format definitions",
              "context": "Context definitions", "formatter": "Formatter definitions",
              "decorator": "Decorator definitions", "Java implementation classes": "Java implementation classes",
              "Additional Java dependencies": "Additional Java dependencies"}
    totals = {key: {} for key in labels}
    for packet in packets:
        for kind, values in inventory.get((packet.channel, packet.operation_id), {}).items():
            totals.setdefault(kind, {}).update(values)
    lines = ["", "Batch composition: distinct dependencies recorded for the selected operations",
             "Totals count each definition or Java class once across this batch.",
             "",
             "Component type | Count", "---------------|------"]
    lines.extend(f"{label} | {len(totals[kind])}" for kind, label in labels.items())
    lines.append("")
    lines.append("Additional Java dependencies are identified by static source analysis; inspect source for dynamic dependencies.")
    if not include_details:
        return lines
    for packet in packets:
        lines.append("\nComponents used by " + packet.channel + " / " + packet.operation_id)
        groups = inventory.get((packet.channel, packet.operation_id))
        if groups is None:
            lines.append("  Inventory evidence unavailable for this operation.")
            continue
        for kind, label in labels.items():
            values = groups.get(kind, {})
            if collapsible and values:
                from agents.migration_planning.collapsible_sections import collapsible_section
                lines.append(collapsible_section(f"{label}: {len(values)}", sorted(values.values())))
            else:
                lines.append(f"  {label}: {len(values)}")
                lines.extend("    - " + name for name in sorted(values.values()))
    return lines
