"""Plan shared libraries from distinct operation consumers, not raw reference counts."""

import json

from models.shared_library_plan import SharedLibrary, SharedLibraryPlan
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.shared_library_plans import save_shared_library_plan
from tools.state_store_tools.component_inventory import get_java_dependency_graph
from tools.component_inventory_tools.dependency_order import plan_dependency_order


def prepare_library_plan(conn, config, profile, migration_plan):
    """Group components by consumer set, with configurable broad-sharing threshold."""
    if not conn.execute("SELECT 1 FROM component_inventory_reports WHERE run_id=?", (config.run_id,)).fetchone():
        return None
    selected = {packet.channel + "/" + packet.operation_id for batch in migration_plan.batches for packet in batch.task_packets}
    consumers = {}
    reference_counts = {}
    operation_origins = {}
    hashes = {}
    definition_implementations = {}
    selected_source_roots = set()
    for row in conn.execute("SELECT record_json FROM source_implementations WHERE run_id=?", (config.run_id,)):
        record = json.loads(row[0])
        hashes["implementation:" + record["implementation_id"]] = record["source_hash"]
    for row in conn.execute("SELECT record_json FROM configured_component_definitions WHERE run_id=?", (config.run_id,)):
        record = json.loads(row[0])
        hashes["definition:" + record["definition_id"]] = record["configuration_hash"]
        definition_implementations["definition:" + record["definition_id"]] = record["implementation_id"]
    for row in conn.execute("SELECT record_json FROM configured_component_uses WHERE run_id=?", (config.run_id,)):
        use = json.loads(row[0])
        consumer = (use["channel"] or "") + "/" + use["operation_id"]
        if consumer in selected and use["implementation_id"]:
            selected_source_roots.add(use["implementation_id"])
        operation_origins.setdefault(consumer, set()).add(use["operation_key"])
        if use["component_kind"] in {"format", "context"}:
            key = "definition:" + use["definition_id"]
        elif use["component_kind"] in {"opStep", "formatter", "decorator"} and use["implementation_id"]:
            key = "implementation:" + use["implementation_id"]
        else:
            continue
        consumers.setdefault(key, set()).add(consumer)
        reference_counts[key] = reference_counts.get(key, 0) + 1
    graph = get_java_dependency_graph(conn, config.run_id)
    for use in graph.uses:
        consumer = (use.channel or "") + "/" + use.operation_id
        operation_origins.setdefault(consumer, set()).add(use.operation_key)
        key = "implementation:" + use.implementation_id
        consumers.setdefault(key, set()).add(consumer)
        reference_counts[key] = reference_counts.get(key, 0) + use.reference_count
    assignments = {}
    groups = {}
    for key, owners in sorted(consumers.items()):
        if not owners.intersection(selected):
            continue
        if reference_counts[key] < profile.shared_library_min_usage:
            assignments[key] = None
        else:
            library = "common-lib" if reference_counts[key] > profile.broad_library_usage_threshold else "shared-" + stable_id(sorted(owners))[:12]
            assignments[key] = library
            groups.setdefault(library, []).append(key)
    conversion_order, library_dependencies, library_build_order, dependency_issues = plan_dependency_order(graph, assignments, definition_implementations)
    fingerprint = stable_id(assignments, {key: hashes[key] for key in assignments},
                            {key: reference_counts[key] for key in assignments}, sorted(selected),
                            profile.shared_library_min_usage, profile.broad_library_usage_threshold, profile.model_name,
                            profile.allowed_ibm_classes, profile.allowed_ibm_artifacts, library_dependencies)
    libraries = [SharedLibrary(library_id=name, component_keys=keys,
        consumers=sorted(set().union(*(consumers[key] for key in keys))),
        version="1.0.0-" + stable_id(config.run_id, name, {key: hashes[key] for key in keys},
            profile.model_name, profile.allowed_ibm_classes, profile.allowed_ibm_artifacts)[:12]) for name, keys in sorted(groups.items())]
    diagnostics = ["Multiple original operations have the same channel/name: " + consumer
                   for consumer, origins in operation_origins.items() if consumer in selected and len(origins) > 1]
    diagnostics.extend(dependency_issues)
    diagnostics.extend(issue.message for issue in graph.issues if issue.implementation_id in selected_source_roots)
    result = SharedLibraryPlan(fingerprint=fingerprint, libraries=libraries, assignments=assignments, diagnostics=sorted(set(diagnostics)),
                              consumers={key: sorted(consumers[key]) for key in assignments},
                              usage_counts={key: reference_counts[key] for key in assignments},
                              shared_library_min_usage=profile.shared_library_min_usage,
                              broad_library_usage_threshold=profile.broad_library_usage_threshold)
    result.conversion_order = conversion_order
    result.library_dependencies = library_dependencies
    result.library_build_order = library_build_order
    save_shared_library_plan(conn, config.run_id, result)
    return result
