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
    from tools.state_store_tools.java_usage import check_detailed_scope
    check_detailed_scope(conn, config.run_id, selected)
    candidates = set()
    for row in conn.execute('SELECT component_kind,implementation_id,channel,operation_id,json_extract(record_json,\'$.definition_id\') FROM configured_component_uses WHERE run_id=?', (config.run_id,)):
        if (row[2] or '') + '/' + row[3] in selected:
            if row[0] in {'format', 'context'}:
                candidates.add('definition:' + row[4])
            if row[1]:
                candidates.add('implementation:' + row[1])
    for row in conn.execute('SELECT implementation_id,channel,operation_id FROM java_dependency_uses WHERE run_id=?', (config.run_id,)):
        if (row[1] or '') + '/' + row[2] in selected:
            candidates.add('implementation:' + row[0])
    conn.execute('CREATE TEMP TABLE IF NOT EXISTS library_plan_candidates (component_key TEXT PRIMARY KEY)')
    conn.execute('CREATE TEMP TABLE IF NOT EXISTS library_plan_operations (consumer TEXT PRIMARY KEY)')
    conn.execute('DELETE FROM library_plan_candidates')
    conn.execute('DELETE FROM library_plan_operations')
    conn.executemany('INSERT INTO library_plan_candidates VALUES (?)', ((key,) for key in candidates))
    conn.executemany('INSERT INTO library_plan_operations VALUES (?)', ((key,) for key in selected))
    consumers = {}
    reference_counts = {}
    operation_origins = {}
    hashes = {}
    definition_implementations = {}
    from tools.state_store_tools.java_usage import mapped_direct_usage, iter_global_direct_usage
    mapped_counts = mapped_direct_usage(conn, config.run_id)
    selected_source_roots = set()
    for row in conn.execute("SELECT record_json FROM source_implementations WHERE run_id=? AND 'implementation:'||implementation_id IN (SELECT component_key FROM library_plan_candidates)", (config.run_id,)):
        record = json.loads(row[0])
        if 'implementation:' + record['implementation_id'] not in candidates:
            continue
        hashes["implementation:" + record["implementation_id"]] = record["source_hash"]
    for row in conn.execute("SELECT record_json FROM configured_component_definitions WHERE run_id=? AND 'definition:'||definition_id IN (SELECT component_key FROM library_plan_candidates)", (config.run_id,)):
        record = json.loads(row[0])
        if 'definition:' + record['definition_id'] not in candidates:
            continue
        hashes["definition:" + record["definition_id"]] = record["configuration_hash"]
        definition_implementations["definition:" + record["definition_id"]] = record["implementation_id"]
    for row in conn.execute("""SELECT record_json FROM configured_component_uses WHERE run_id=? AND (
        'implementation:'||implementation_id IN (SELECT component_key FROM library_plan_candidates) OR
        'definition:'||json_extract(record_json,'$.definition_id') IN (SELECT component_key FROM library_plan_candidates) OR
        COALESCE(channel,'')||'/'||operation_id IN (SELECT consumer FROM library_plan_operations))""", (config.run_id,)):
        use = json.loads(row[0])
        consumer = (use["channel"] or "") + "/" + use["operation_id"]
        if consumer in selected and use["implementation_id"]:
            selected_source_roots.add(use["implementation_id"])
        operation_origins.setdefault(consumer, set()).add(use["operation_key"])
        keys = []
        if use["component_kind"] in {"format", "context"}:
            keys.append("definition:" + use["definition_id"])
        if use["component_kind"] in {"operation", "opStep", "formatter", "decorator", "context"} and use["implementation_id"]:
            keys.append("implementation:" + use["implementation_id"])
        for key in keys:
            if key not in candidates:
                continue
            if mapped_counts:
                continue
            consumers.setdefault(key, set()).add(consumer)
            reference_counts[key] = reference_counts.get(key, 0) + 1
    for key, origin, name, channel, count in iter_global_direct_usage(conn, config.run_id):
        consumer = (channel or '') + '/' + name
        operation_origins.setdefault(consumer, set()).add(origin)
        consumers.setdefault(key, set()).add(consumer)
        reference_counts[key] = reference_counts.get(key, 0) + count
    roots = {key.removeprefix('implementation:') for key in candidates if key.startswith('implementation:')}
    graph = get_java_dependency_graph(conn, config.run_id, include_uses=False, roots=roots)
    from tools.state_store_tools.java_usage import iter_global_java_usage
    for use in iter_global_java_usage(conn, config.run_id, candidates=True):
        consumer = (use.channel or "") + "/" + use.operation_id
        operation_origins.setdefault(consumer, set()).add(use.operation_key)
        key = "implementation:" + use.implementation_id
        consumers.setdefault(key, set()).add(consumer)
        reference_counts[key] = reference_counts.get(key, 0) + use.reference_count
    assignments = {}
    groups = {}
    consumer_counts = {key: len(owners) for key, owners in consumers.items()}
    for key, owners in sorted(consumers.items()):
        if not owners.intersection(selected):
            continue
        if consumer_counts[key] < profile.shared_library_min_usage:
            assignments[key] = None
        else:
            library = "common-lib" if consumer_counts[key] > profile.broad_library_usage_threshold else "shared-" + stable_id(sorted(owners))[:12]
            assignments[key] = library
            groups.setdefault(library, []).append(key)
    conversion_order, library_dependencies, library_build_order, dependency_issues = plan_dependency_order(graph, assignments, definition_implementations)
    fingerprint = stable_id(assignments, {key: hashes[key] for key in assignments},
                            {key: consumer_counts[key] for key in assignments}, sorted(selected),
                            profile.shared_library_min_usage, profile.broad_library_usage_threshold, profile.model_name,
                            profile.allowed_ibm_classes, profile.allowed_ibm_artifacts, library_dependencies,
                            getattr(profile, "java_version", "25"), getattr(profile, "java_home", None))
    libraries = [SharedLibrary(library_id=name, component_keys=keys,
        consumers=sorted(set().union(*(consumers[key] for key in keys))),
        version="1.0.0-" + stable_id(config.run_id, name, {key: hashes[key] for key in keys},
            profile.model_name, profile.allowed_ibm_classes, profile.allowed_ibm_artifacts,
            getattr(profile, "java_version", "25"), getattr(profile, "java_home", None))[:12]) for name, keys in sorted(groups.items())]
    diagnostics = ["Multiple original operations have the same channel/name: " + consumer
                   for consumer, origins in operation_origins.items() if consumer in selected and len(origins) > 1]
    diagnostics.extend(dependency_issues)
    diagnostics.extend(issue.message for issue in graph.issues if issue.implementation_id in selected_source_roots)
    result = SharedLibraryPlan(fingerprint=fingerprint, libraries=libraries, assignments=assignments, diagnostics=sorted(set(diagnostics)),
                              consumers={key: sorted(consumers[key]) for key in assignments},
                              usage_counts={key: consumer_counts[key] for key in assignments},
                              reference_counts={key: reference_counts[key] for key in assignments},
                              shared_library_min_usage=profile.shared_library_min_usage,
                              broad_library_usage_threshold=profile.broad_library_usage_threshold)
    result.conversion_order = conversion_order
    result.library_dependencies = library_dependencies
    result.library_build_order = library_build_order
    save_shared_library_plan(conn, config.run_id, result)
    return result
