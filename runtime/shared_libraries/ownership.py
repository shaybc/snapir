"""Resolve component task ownership from the original inventory and library plan."""

import json
import hashlib
from pathlib import Path

from tools.state_store_tools.shared_library_plans import get_shared_library_plan


def component_project(config, data, channel):
    """Return the canonical library or service directory for a conversion task."""
    library = data.get("managed_library_id")
    if library:
        if Path(library).name != library or ":" in library or library in {".", ".."}:
            raise ValueError("Invalid managed library identity")
        return Path(config.output_root) / "common-lib" if library == "common-lib" else Path(config.output_root) / "libraries" / library
    owner = data.get("managed_project_operation")
    return Path(config.output_root) / channel / owner if owner else Path(config.output_root) / "common-lib"


def task_binding(conn, config, closure, kind, logical_id, source_file=None):
    """Bind one closure unit to its exact source identity or configured definition."""
    plan = get_shared_library_plan(conn, config.run_id)
    if plan is None:
        return {}
    consumer = closure["channel"] + "/" + closure["operation_id"]
    if kind == "ibm_java":
        relative = Path(source_file).resolve().relative_to(Path(config.source_root).resolve()).as_posix()
        matches = [json.loads(row[0]) for row in conn.execute("SELECT record_json FROM source_implementations WHERE run_id=?", (config.run_id,))]
        matches = [record for record in matches if record["source_path"] == relative]
        if len(matches) != 1:
            raise ValueError("Source implementation identity is missing or ambiguous: " + logical_id)
        key = "implementation:" + matches[0]["implementation_id"]
        source_hash = matches[0]["source_hash"]
        if hashlib.sha256(Path(source_file).read_bytes()).hexdigest() != source_hash:
            raise ValueError("Java source changed after inventory; refresh inventory before conversion")
    else:
        expected_kind = "format" if kind == "xml_fmtdef" else "context"
        definitions = {row[0]: json.loads(row[1]) for row in conn.execute("SELECT definition_id,record_json FROM configured_component_definitions WHERE run_id=?", (config.run_id,))}
        uses = [json.loads(row[0]) for row in conn.execute("SELECT record_json FROM configured_component_uses WHERE run_id=? AND operation_id=? AND channel=?",
                                                        (config.run_id, closure["operation_id"], closure["channel"]))]
        ids = {use["definition_id"] for use in uses if use["component_kind"] == expected_kind and
               definitions[use["definition_id"]]["logical_id"] == logical_id}
        if len(ids) != 1:
            raise ValueError("Configured definition is missing or ambiguous: " + logical_id)
        record = definitions[ids.pop()]
        key = "definition:" + record["definition_id"]
        source_hash = record["configuration_hash"]
    if key not in plan.assignments:
        raise ValueError("Component is outside the reviewed library plan: " + logical_id)
    result = dict(source_component_key=key, source_component_hash=source_hash,
                managed_library_id=plan.assignments[key], consumer_operations=plan.consumers[key],
                library_plan_fingerprint=plan.fingerprint)
    if kind == "xml_fmtdef":
        result["configured_source_xml"] = record["configuration_xml"]
    return result


def task_covers(data, operation_id, channel):
    """Check declared consumers, retaining compatibility with old task inputs."""
    if data.get("managed_project_operation") is not None:
        return (data["managed_project_operation"], data.get("channel")) == (operation_id, channel)
    if data.get("consumer_operations") is not None:
        return channel + "/" + operation_id in data["consumer_operations"]
    return data.get("managed_project_operation") is None or (
        data.get("managed_project_operation"), data.get("channel")) == (operation_id, channel)
