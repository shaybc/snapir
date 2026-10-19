"""Collect complete-format and configured-step evidence from a checked closure."""

import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from models.behavior_unit import BehaviorUnitInput, SourceEvidence
from tools.state_store_tools.component_inventory import get_conversion_inventory
from tools.component_inventory_tools.identity import stable_id


def build_behavior_units(conn, config, closure, profile=None):
    """Return configured units and routing-name bindings without scheduling legacy tags."""
    if closure["status"] != "READY" or not closure.get("conversion_components_checked"):
        raise ValueError("Behavior conversion requires a checked READY evidence closure")
    from tools.conversion_tools.conversion_component_set import checked_conversion_units
    checked_conversion_units(closure)
    from tools.conversion_tools.behavior_evidence_freshness import verify_configuration_sources
    verify_configuration_sources(conn, config, closure["operation_id"], closure["channel"])
    implementations, uses, graph = get_conversion_inventory(conn, config.run_id, closure["operation_id"], closure["channel"])
    definitions = {row[0]: json.loads(row[1]) for row in conn.execute(
        "SELECT definition_id,record_json FROM configured_component_definitions WHERE run_id=?", (config.run_id,))}
    outgoing = {}
    for edge in graph.get("dependencies", []):
        outgoing.setdefault(edge["caller_implementation_id"], set()).add(edge["target_implementation_id"])
    checked = {str(Path(item["source_file"]).resolve()): item for item in closure["conversion_components"]
               if item["kind"] == "ibm_java"}
    consumer = closure["channel"] + "/" + closure["operation_id"]
    workspace_uses = [json.loads(row[0]) for row in conn.execute(
        "SELECT record_json FROM configured_component_uses WHERE run_id=?", (config.run_id,))]
    operation_formats = {(json.loads(row[1]).get("channel"), row[0]): json.loads(row[1]).get("ref_formats", {})
        for row in conn.execute("SELECT logical_id,metadata_json FROM source_artifacts WHERE run_id=? AND kind='operation'", (config.run_id,))}

    def step_configuration(xml):
        node = ET.fromstring(xml)
        for name in list(node.attrib):
            if name == "id" or name.startswith("on"):
                del node.attrib[name]
        node.tail = None
        return ET.tostring(node, encoding="unicode")

    operation_uses, step_candidates = {}, {}
    for use in workspace_uses:
        operation_uses.setdefault(use["operation_key"], []).append(use)
        if use["component_kind"] == "opStep":
            step_candidates.setdefault((use.get("implementation_id"), step_configuration(use["configuration_xml"])), []).append(use)

    def step_dependencies(use):
        prefix = use["referenced_by"] + " -> " + use["definition_path"] + use["definition_selector"] + "/"
        return [item for item in operation_uses[use["operation_key"]] if item["referenced_by"].startswith(prefix)]

    def dependency_identity(related):
        return sorted({(item["component_kind"], item.get("implementation_id") or item.get("resolution_issue") or "",
                        item["configuration_hash"]) for item in related})

    def evidence(selected):
        pending = {use["implementation_id"] for use in selected if use.get("implementation_id")}
        visited, result = set(), []
        while pending:
            identity = pending.pop()
            if identity in visited:
                continue
            visited.add(identity)
            item = implementations[identity]
            path = (Path(config.source_root) / item["source_path"]).resolve()
            original = checked.get(str(path))
            if original:
                content = path.read_text(encoding="utf-8-sig")
                result.append(SourceEvidence(identity=original["logical_id"], content=content,
                    content_hash=hashlib.sha256(path.read_bytes()).hexdigest()))
                pending.update(outgoing.get(identity, set()))
        return sorted(result, key=lambda item: item.identity)

    def make(kind, logical, xml, selected):
        sources = evidence(selected)
        node = ET.fromstring(xml)
        # Routing belongs to the operation; business configuration belongs to the step.
        if kind == "configured_step":
            for name in list(node.attrib):
                if name == "id" or name.startswith("on"):
                    del node.attrib[name]
        node.tail = None
        canonical = ET.tostring(node, encoding="unicode")
        referenced = [definitions[key] for key in sorted({use["definition_id"] for use in selected
            if use["component_kind"] in {"format", "context"}})] if kind == "configured_step" else []
        original = "\n".join([canonical, *(source.content for source in sources),
            *(use.get("resolution_issue") or "" for use in selected)])
        records = [item for item in closure.get("external_dependencies", [])
            if re.search(r"\b" + re.escape(item["class_name"].rsplit(".", 1)[-1]) + r"\b", original)]
        external_identity = sorted({json.dumps({key: value for key, value in item.items()
            if key not in ("origin", "originating_tag", "source_file", "usage", "referenced_by")}, sort_keys=True)
            for item in records})
        fingerprint = stable_id(kind, canonical, [(item.identity, item.content_hash) for item in sources], external_identity,
                                sorted(item["configuration_hash"] for item in referenced))
        operation_calls = [call for call in closure.get('operation_calls', []) if kind == 'configured_step' and call['step'] == logical]
        if operation_calls:
            fingerprint = stable_id(fingerprint, operation_calls)
        unit = BehaviorUnitInput(unit_id=kind + "-" + fingerprint[:24], kind=kind, logical_id=logical,
            configuration_xml=xml, sources=sources, consumers=[consumer], fingerprint=fingerprint,
            external_dependencies=records, referenced_definitions=referenced, operation_calls=operation_calls)
        from runtime.behavior_conversion.service_connection_evidence import attach_unit_connections
        if operation_calls:
            return unit
        return attach_unit_connections(conn, config, closure, unit, profile)

    units, bindings = [], {}
    for use in uses:
        if use["component_kind"] == "opStep":
            name = ET.fromstring(use["configuration_xml"]).get("id")
            if name not in closure["included_opstep_ids"]:
                continue
            related = step_dependencies(use)
            unit = make("configured_step", name, use["configuration_xml"], [use, *related])
            unit.consumers = sorted({consumer, *(item["channel"] + "/" + item["operation_id"]
                for item in step_candidates[(use.get("implementation_id"), step_configuration(use["configuration_xml"]))]
                if dependency_identity(step_dependencies(item)) == dependency_identity(related))})
            if unit.operation_calls:
                unit.consumers = [consumer]
            if unit.service_connections:
                # Same Java/configuration in another channel may resolve a different
                # service instance. Count only proven compatible channel consumers.
                unit.consumers = [name for name in unit.consumers if name.split('/', 1)[0] == closure['channel']]
            units.append(unit)
            bindings[name] = unit.unit_id
    for role, kind in (("csRequestFormat", "request_unformat"), ("csReplyFormat", "response_format"),
                       ("csErrorReplyFormat", "response_format")):
        name = closure.get("ref_formats", {}).get(role)
        if not name:
            continue
        roots = [use for use in uses if use["component_kind"] == "format"
                 and definitions[use["definition_id"]]["logical_id"] == name]
        identities = {use["definition_id"] for use in roots}
        if len(identities) != 1:
            raise ValueError("Complete format definition is missing or ambiguous: " + name)
        root = roots[0]
        # referenced_by retains the recursive refFormat path, including nested formats.
        selected = [use for use in uses if use["referenced_by"].startswith(root["referenced_by"])
                    or (use["definition_path"] == root["definition_path"] and
                        use["definition_selector"].startswith(root["definition_selector"] + "/"))]
        definition = definitions[root["definition_id"]]
        nested = [definitions[use["definition_id"]] for use in selected if use["component_kind"] == "format"
                  and use["definition_id"] != root["definition_id"]]
        xml = definition["configuration_xml"]
        if nested:
            node = ET.Element("formatEvidence")
            node.append(ET.fromstring(xml))
            for item in {value["definition_id"]: value for value in nested}.values():
                node.append(ET.fromstring(item["configuration_xml"]))
            xml = ET.tostring(node, encoding="unicode")
        unit = make(kind, name, xml, selected)
        matching_roles = {"csRequestFormat"} if kind == "request_unformat" else {"csReplyFormat", "csErrorReplyFormat"}
        unit.consumers = sorted({consumer, *(item["channel"] + "/" + item["operation_id"]
            for item in workspace_uses if item["component_kind"] == "format" and item["definition_id"] == root["definition_id"]
            and any(operation_formats.get((item["channel"], item["operation_id"]), {}).get(key) == name
                    for key in matching_roles))})
        if unit.service_connections:
            unit.consumers = [name for name in unit.consumers if name.split('/', 1)[0] == closure['channel']]
        units.append(unit)
        bindings[role] = unit.unit_id
    if not units:
        raise ValueError("No configured behavior units were discovered")
    return units, bindings
