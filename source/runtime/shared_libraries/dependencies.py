"""Bind source dependencies to conversion tasks and their compiled native APIs."""

import hashlib
import json
from pathlib import Path

from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.component_inventory import get_java_dependency_graph
from tools.state_store_tools.shared_library_plans import get_shared_library_plan


class UtilityNotReadyError(ValueError):
    """A scheduled utility must finish conversion or recompilation before its caller."""


def dependency_binding(conn, config, source_key, external_dependencies=()):
    """Fingerprint the transitive original inputs while retaining direct conversion dependencies."""
    if not source_key:
        return {}
    root = source_key.removeprefix("implementation:") if source_key.startswith("implementation:") else None
    if root is None and source_key.startswith("definition:"):
        row = conn.execute("SELECT implementation_id FROM configured_component_definitions WHERE run_id=? AND definition_id=?",
                           (config.run_id, source_key.removeprefix("definition:"))).fetchone()
        root = row[0] if row else None
    if not root:
        return {}
    graph = get_java_dependency_graph(conn, config.run_id, include_uses=False)
    outgoing = {}
    for edge in graph.dependencies:
        outgoing.setdefault(edge.caller_implementation_id, set()).add(edge.target_implementation_id)
    external_names = {item["class_name"] for item in external_dependencies}
    if external_names:
        external_ids = set()
        for row in conn.execute("SELECT implementation_id,record_json FROM source_implementations WHERE run_id=?", (config.run_id,)):
            item = json.loads(row["record_json"])
            name = ".".join(filter(None, [item.get("package_name"), item["class_name"]]))
            if name in external_names:
                external_ids.add(row["implementation_id"])
        outgoing = {key: values - external_ids for key, values in outgoing.items()}
    if not outgoing.get(root):
        return {}
    visited = set()
    pending = list(outgoing[root])
    hashes = {}
    while pending:
        identity = pending.pop()
        if identity in visited:
            continue
        visited.add(identity)
        row = conn.execute("SELECT record_json FROM source_implementations WHERE run_id=? AND implementation_id=?",
                           (config.run_id, identity)).fetchone()
        if row is None:
            raise ValueError("Original Java dependency identity is missing")
        source = json.loads(row[0])
        path = (Path(config.source_root) / source["source_path"]).resolve()
        if not path.is_relative_to(Path(config.source_root).resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != source["source_hash"]:
            raise ValueError("Java utility source changed after inventory; refresh inventory")
        hashes[identity] = source["source_hash"]
        pending.extend(outgoing.get(identity, []))
    return dict(dependency_component_keys=sorted("implementation:" + identity for identity in outgoing[root]),
                dependency_source_hash=stable_id(sorted(hashes.items())))


def ordered_conversion_tasks(conn, config, rows):
    """Order shared projects and their classes before consumers, preserving legacy queues."""
    plan = get_shared_library_plan(conn, config.run_id)
    if not plan or not plan.conversion_order:
        return sorted(rows, key=lambda row: bool(json.loads(row["input_json"] or "{}").get("managed_project_operation")))
    if plan.diagnostics:
        raise ValueError("Reviewed library dependency plan has unresolved diagnostics")
    ranks = {key: index for index, key in enumerate(plan.conversion_order)}
    library_ranks = {name: index for index, name in enumerate(plan.library_build_order)}
    def order(row):
        data = json.loads(row["input_json"] or "{}")
        owner = data.get("managed_project_operation")
        return (bool(owner), library_ranks.get(data.get("managed_library_id") or "common-lib", -1) if not owner else 0,
                ranks.get(data.get("source_component_key"), -1), row["created_at"], row["task_id"])
    return sorted(rows, key=order)


def ordered_review_projects(conn, config, projects):
    """Build planned utility libraries in dependency order before service projects."""
    plan = get_shared_library_plan(conn, config.run_id)
    ranks = {name: index for index, name in enumerate(plan.library_build_order)} if plan else {}
    def order(value):
        path = Path(value)
        library = path.name == "common-lib" or path.parent.name == "libraries"
        return (not library, ranks.get(path.name, -1), value)
    return sorted(projects, key=order)


def converted_dependency_apis(conn, config, data):
    """Require each direct dependency in the same project or an eligible planned library."""
    result = []
    plan = get_shared_library_plan(conn, config.run_id)
    for key in data.get("dependency_component_keys", []):
        dependency = None
        for row in conn.execute("SELECT task_id,input_json,status FROM agent_tasks WHERE run_id=? AND agent_name='ManagedConversion'",
                                (config.run_id,)):
            candidate = json.loads(row["input_json"] or "{}")
            if candidate.get("source_component_key") != key:
                continue
            library = candidate.get("managed_library_id")
            if plan and library != plan.assignments.get(key):
                continue
            same_operation = (candidate.get("managed_project_operation"), candidate.get("channel")) == (
                data.get("managed_project_operation"), data.get("channel"))
            if library is None and not same_operation:
                continue
            if data.get("managed_library_id") and library != data["managed_library_id"] and (
                    not plan or library not in plan.library_dependencies.get(data["managed_library_id"], [])):
                continue
            if row["status"] not in {"completed", "validated"}:
                continue
            artifact = conn.execute("SELECT artifact_path,compiles,status FROM native_java_artifacts WHERE run_id=? AND artifact_id=?",
                (config.run_id, f"{config.run_id}:native_java:{row['task_id']}")).fetchone()
            if not artifact or not artifact["compiles"] or artifact["status"] not in {"converted", "validated"}:
                continue
            from runtime.shared_libraries.ownership import component_project
            path = Path(artifact["artifact_path"]).resolve()
            if not path.is_relative_to(component_project(config, candidate, candidate["channel"]).resolve() / "src/main/java"):
                raise ValueError("Converted utility is outside its planned project")
            source = path.read_bytes()
            value = dict(source_component_key=key, logical_id=candidate["conversion_id"], library_id=library,
                         java_source=source.decode("utf-8"), source_hash=hashlib.sha256(source).hexdigest())
            if dependency is not None:
                raise ValueError("Multiple eligible converted utility implementations")
            dependency = value
        if dependency is None:
            raise UtilityNotReadyError("Required Java utility is not yet converted: " + key)
        result.append(dependency)
    return result
