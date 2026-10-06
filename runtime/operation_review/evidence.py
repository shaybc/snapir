"""Collect channel-qualified assembly inputs and review fingerprints."""

import hashlib
import json
import re
from pathlib import Path

from agents.operation_assembly.service_skeleton_generator.agent import load_service_skeleton_plans
from runtime.component_review.evidence import collect_component_evidence
from tools.state_store_tools.operation_closures import get_operation_closure
from tools.state_store_tools._json import loads


def collect_operation_evidence(conn, config, profile, plan):
    """Require intact compiled assembly snapshots for every selected operation."""
    components = collect_component_evidence(conn, config, profile)
    items = []
    for batch in plan.batches:
        for packet in batch.task_packets:
            identity = f"{config.run_id}:{packet.channel}:{packet.operation_id}"
            assembly_task_id = "assembly-" + hashlib.sha256(identity.encode()).hexdigest()
            item = dict(operation_id=packet.operation_id, channel=packet.channel, assembly_task_id=assembly_task_id,
                        issues=[], service_path=None, project=str((Path(config.output_root) / packet.channel / packet.operation_id).resolve()))
            try:
                snapshot = conn.execute("SELECT * FROM operation_assembly_snapshots WHERE run_id=? AND operation_id=? AND channel=?",
                                        (config.run_id, packet.operation_id, packet.channel)).fetchone()
                if snapshot is None:
                    raise ValueError("Successful assembly checkpoint is missing")
                task = conn.execute("SELECT * FROM agent_tasks WHERE task_id=? AND run_id=? AND channel=?",
                                    (assembly_task_id, config.run_id, packet.channel)).fetchone()
                if task is None or task["status"] != "completed":
                    raise ValueError("Assembly task is not successfully completed")
                path = Path(snapshot["service_path"]).resolve()
                if not path.is_relative_to(Path(item["project"]) / "src/main/java"):
                    raise ValueError("Assembly output is outside its managed service project")
                item["service_path"] = str(path)
                item["java_source"] = path.read_text(encoding="utf-8")
                item["service_hash"] = hashlib.sha256(path.read_bytes()).hexdigest()
                item["pom_hash"] = hashlib.sha256((Path(item["project"]) / "pom.xml").read_bytes()).hexdigest()
                if item["service_hash"] != snapshot["service_hash"] or item["pom_hash"] != snapshot["pom_hash"]:
                    item["issues"].append("Assembly source or POM changed since its successful build")
                routing, context, serialization = load_service_skeleton_plans(conn, packet.operation_id, packet.channel, config.run_id)
                item.update(routing=routing, context=context, serialization=serialization)
                closure = get_operation_closure(conn, packet.operation_id, packet.channel, config.run_id)
                if closure is None or closure["status"] != "READY":
                    raise ValueError("Operation closure is no longer READY")
                xml_path = Path(closure["closure_json"].get("source_xml_path", ""))
                if not xml_path.is_absolute():
                    xml_path = Path(config.source_root) / xml_path
                item["original_xml"] = xml_path.read_text(encoding="utf-8")
                inputs = loads(task["input_json"], {}) or {}
                for key, current in (("operation_xml", item["original_xml"]), ("routing_plan", routing.model_dump(mode="json")),
                                     ("context_plan", context.model_dump(mode="json")), ("serialization_plan", serialization.model_dump(mode="json"))):
                    if inputs.get(key) != current:
                        item["issues"].append("Assembly input changed: " + key)
                supporting = [component for component in components if component["task_input"].get("managed_project_operation") is None or
                              (component["task_input"].get("managed_project_operation"), component["task_input"].get("channel")) ==
                              (packet.operation_id, packet.channel)]
                if not supporting or any(component["issues"] for component in supporting):
                    item["issues"].append("Approved component evidence is missing or stale")
                item["components"] = [dict(kind=value["kind"], logical_id=value["conversion_id"], java_source=value["converted_source"],
                                           fingerprint=value["fingerprint"]) for value in supporting]
                reply_id = closure["closure_json"].get("ref_formats", {}).get("csReplyFormat")
                item["expected_return_type"] = None
                for component in supporting:
                    if component["kind"] == "xml_fmtdef" and component["conversion_id"] == reply_id:
                        declaration = re.search(r"\bpublic\s+(?:final\s+)?class\s+(\w+)", component["converted_source"])
                        if declaration:
                            package = re.search(r"\bpackage\s+([\w.]+)\s*;", component["converted_source"])
                            item["expected_return_type"] = ((package.group(1) + ".") if package else "") + declaration.group(1)
                if "TODO" in item["java_source"] or "UnsupportedOperationException" in item["java_source"]:
                    item["issues"].append("Assembled service contains unfinished implementation")
                payload = dict(operation_id=packet.operation_id, channel=packet.channel, original_xml=item["original_xml"],
                               java_source=item["java_source"], routing_plan=routing.model_dump(mode="json"),
                               context_plan=context.model_dump(mode="json"), serialization_plan=serialization.model_dump(mode="json"),
                               components=item["components"], expected_return_type=item["expected_return_type"],
                               pom_hash=item["pom_hash"], closure=closure["closure_json"],
                               model=profile.model_name, provider=profile.model_provider,
                               allowed_ibm_classes=profile.allowed_ibm_classes, allowed_ibm_artifacts=profile.allowed_ibm_artifacts,
                               repositories=profile.approved_maven_repository_urls, review_contract="1")
                item["payload"] = payload
                item["fingerprint"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            except Exception as exc:
                item["issues"].append(str(exc))
                item["fingerprint"] = "unavailable"
            items.append(item)
    return items
