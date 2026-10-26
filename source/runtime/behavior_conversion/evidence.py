"""Expose accepted native operation snapshots to existing packaging/finalization."""

import json
from pathlib import Path
from types import SimpleNamespace
from runtime.behavior_conversion.bundle_output import verify_manifest
from tools.state_store_tools.behavior_units import snapshot
from tools.component_inventory_tools.identity import stable_id


def collect_native_operation_evidence(conn, config, profile, plan):
    """Require exact accepted sources, current contracts, and passing reviews."""
    items = []
    for batch in plan.batches:
        for packet in batch.task_packets:
            identity = packet.channel + "/" + packet.operation_id
            item = dict(operation_id=packet.operation_id, channel=packet.channel, issues=[], fingerprint="unavailable",
                        project=str(Path(config.output_root) / packet.channel / packet.operation_id))
            try:
                record = snapshot(conn, config.run_id, "operation", identity)
                if record is None or record["status"] != "accepted":
                    raise ValueError("Accepted native operation snapshot is missing")
                data = json.loads(record["data_json"])
                if data['closure'].get('operation_calls'):
                    from runtime.behavior_conversion.operation_calls import verify_operation_contracts
                    verify_operation_contracts(conn, config, data['closure']['operation_calls'], profile)
                from runtime.behavior_conversion.service_connection_freshness import verify_connection_sources
                verify_connection_sources(config, profile, data.get('service_connections', []))
                from tools.conversion_tools.behavior_evidence_freshness import verify_configuration_sources
                from tools.conversion_tools.conversion_component_set import checked_conversion_units
                scoped = data['closure'].get('scoped_workflow')
                if scoped:
                    from runtime.scoped_native.scope import verify_context
                    verify_context(conn, config, profile, identity)
                    from runtime.scoped_native.results import verify_operation
                    verify_operation(conn, config, profile, identity, data)
                    if scoped['operation_key'] != identity:
                        raise ValueError('Native snapshot has a different scoped execution context')
                else:
                    verify_configuration_sources(conn, config, packet.operation_id, packet.channel)
                    checked_conversion_units(data["closure"])
                verify_manifest(data["project"], data["files"])
                verify_manifest(data["contract_project"], data["contract_files"])
                for binding in data["bindings"].values():
                    verify_manifest(binding["project"], binding["files"])
                for project in {data["project"], data["contract_project"], *(binding["project"] for binding in data["bindings"].values())}:
                    build = snapshot(conn, config.run_id, "project", project)
                    if build is None:
                        raise ValueError("Accepted native project build manifest is missing")
                    verify_manifest(project, json.loads(build["data_json"])["files"])
                if not data["review"]["approved"] or data["review"]["issues"] or data["review"]["unresolved_questions"]:
                    raise ValueError("Native operation review is not accepted")
                source = Path(data["project"]) / "src/main/java" / (data["service_api"]["type_name"].replace(".", "/") + ".java")
                item.update(service_path=str(source), java_source=source.read_text(encoding="utf-8"),
                    original_xml=data["closure"].get("source_xml_path", ""), components=[],
                    routing=SimpleNamespace(model_dump=lambda routing=data["closure"]["routing_graph"], **_: routing))
                if scoped:
                    from tools.composer_mapper_tools.scoped_vault_access import ScopedVaultAccess
                    from tools.conversion_tools.scoped_closure.source_evidence import SourceEvidence
                    from xml.etree import ElementTree
                    access = ScopedVaultAccess(conn, config.run_id)
                    context = access.operation(packet.channel, packet.operation_id)
                    reference = access.resource(context, 'operations:' + packet.operation_id)
                    item['original_xml'] = ElementTree.tostring(SourceEvidence(config.source_root).xml(reference), encoding='unicode')
                else:
                    path = Path(item["original_xml"])
                    if not path.is_absolute():
                        path = Path(config.source_root) / path
                    item["original_xml"] = path.read_text(encoding="utf-8-sig")
                item["payload"] = {key: value for key, value in data.items() if key != "closure"}
                from tools.state_store_tools.operation_calls import load_graph
                graph = load_graph(conn, config.run_id)
                from runtime.intake_plan import has_intake_plan
                if has_intake_plan(conn, config.run_id) or (graph and any(call['callee'] == identity or call['caller'] == identity for call in graph['calls'])):
                    from runtime.behavior_conversion.operation_calls import attach_operation_calls
                    attach_operation_calls(conn, config, item['payload'], data['closure'].get('operation_calls', []), identity)
                item["fingerprint"] = stable_id(data, (Path(data["project"]) / "pom.xml").read_text(encoding="utf-8"),
                                                profile.java_version, profile.java_home)
            except Exception as exc:
                item["issues"].append(str(exc))
            items.append(item)
    return items
