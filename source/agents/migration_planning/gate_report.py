"""Translate Gate One planning evidence into a reviewable human report."""

import json
import re


GROUP_EXPLANATIONS = {
    "one_step": "A single processing step with no branching is expected.",
    "multi_step_linear": "Several processing steps are expected to run in sequence.",
    "branch_heavy": "The planner expects several conditional paths. Review the recorded step outcomes below.",
    "db_bound": "The operation depends on database or stored-procedure work that must be preserved.",
    "shared_format_context": "The operation uses data formats or context shared with other operations.",
    "unusual_manual_review": "The planner identified unusual behavior that warrants additional review.",
}


def outcome_description(label):
    """Translate Composer routing syntax without inventing business meanings."""
    if label == "onOtherDo":
        return "Any other result"
    if label == "onTimeoutDo":
        return "Timeout"
    match = re.fullmatch(r"on(-?\d+)Do", label)
    if match:
        return "Return code " + match.group(1)
    return "Recorded condition " + label


def planning_summary(plan, config, operations, composition=None, collapsible=False):
    """State the decision and explain scope, batches, classifications and blockers."""
    lines = ["GATE ONE: REVIEW THE PROPOSED MIGRATION PLAN", "",
             "Decision: Do you approve the operations, batch order and component ownership proposed below?",
             "Approval accepts this plan as the basis for conversion.", "", "MIGRATION SCOPE",
             "Selected channels: " + ", ".join(config.target_channels),
             "Requested operations: " + (", ".join(config.include_operations) if config.include_operations else "All eligible operations in the selected channels"),
             "Excluded operations: " + (", ".join(config.exclude_operations) if config.exclude_operations else "None"),
             f"Proposed operations: {sum(len(batch.task_packets) for batch in plan.batches)}",
             f"Proposed batches: {len(plan.batches)}", ""]
    evidence = {(item.get("channel"), item["operation_id"]): item for item in operations}
    for index, batch in enumerate(plan.batches, 1):
        lines.append(f"Batch {index}" + (" (pilot: the first conversion batch)" if batch.is_pilot else ""))
        for packet in batch.task_packets:
            lines.append(f"- {packet.channel} / {packet.operation_id}; target: {packet.target_language.value}")
            lines.append("  Planner classification: " + packet.group.value.replace("_", " "))
            lines.append("  Meaning: " + GROUP_EXPLANATIONS.get(packet.group.value, "Review the planner's classification."))
            item = evidence.get((packet.channel, packet.operation_id), {})
            if "step_count" in item:
                lines.append(f"  Recorded evidence: {item['step_count']} steps; {item.get('branch_count', 0)} distinct transition labels across those steps.")
                lines.append("  Transition labels identify the results that determine the next step.")
            lines.append(f"  References to formats shared with other operations: {item.get('shared_formats_count', 'unavailable')}.")
            for note in packet.generation_notes:
                lines.append("  Planner assessment: " + note.replace("_", " "))
        from agents.migration_planning.batch_composition import composition_lines
        lines.extend(composition_lines(batch.task_packets, composition, collapsible=collapsible))
        lines.append("")
    blocked = [item for item in operations if item.get("has_blocked_context")]
    lines.extend(["BLOCKERS AND APPROVAL", f"Operations with blocked context dependencies: {len(blocked)}."])
    for item in blocked:
        lines.append("- Review blocked context for " + item.get("channel", "") + " / " + item["operation_id"])
    lines.extend(["Gate One requires a decision according to the configured approval policy.",
                  "", "WHAT TO REVIEW",
                  "1. Confirm that only the intended operations and channels are proposed.",
                  "2. Check the recorded steps and outcomes against the legacy operation.",
                  "3. Review which named components will be shared and which will remain operation-local.",
                  "4. Resolve any diagnostics or missing evidence before approving.", ""])
    return "\n".join(lines)


def component_and_routing_report(conn, run_id, plan, libraries, include_ownership=True, include_routing=True, collapsible=False):
    """Resolve machine identities and show source-backed routing and ownership."""
    selected = {packet.channel + "/" + packet.operation_id for batch in plan.batches for packet in batch.task_packets}
    lines = ["RECORDED LEGACY STEPS AND OUTCOMES",
             "The following steps and outcomes were extracted from the legacy source."]
    rows = conn.execute("SELECT logical_id, metadata_json FROM source_artifacts WHERE run_id=? AND kind='opStep' ORDER BY logical_id", (run_id,)).fetchall()
    for consumer in sorted(selected):
        channel, operation = consumer.split("/", 1)
        lines.append("\n" + consumer)
        found = False
        for row in rows:
            metadata = json.loads(row[1]) if row[1] else {}
            source = metadata.get("source_file", "")
            if metadata.get("parent_operation_id") != operation:
                continue
            if source and f"/Channel/{channel}/" not in source.replace("\\", "/"):
                continue
            found = True
            step_lines = ["Implementation: " + (metadata.get("impl_class") or "not recorded")]
            for label, destination in (metadata.get("transitions") or {}).items():
                step_lines.append(outcome_description(label) + " -> " + ("Finish the operation" if destination == "end" else "Go to step " + str(destination)))
            if not metadata.get("transitions"):
                step_lines.append("No transition details recorded; verify against the source.")
            if source:
                step_lines.append("Source: " + source)
            if collapsible:
                from agents.migration_planning.collapsible_sections import collapsible_section
                lines.append(collapsible_section("Step: " + row[0], step_lines))
            else:
                lines.append("- Step: " + row[0] + "; implementation: " + (metadata.get("impl_class") or "not recorded"))
                lines.extend("  " + line for line in step_lines[1:])
        if not found:
            lines.append("- No matching step evidence available; inspect the legacy source before approving.")
    if not include_ownership:
        return "\n".join(lines)
    if not include_routing:
        lines = []
    if libraries is None:
        return "\n".join(lines + ["", "SHARED COMPONENTS", "No shared-library inventory is available for this run."])
    names = {}
    for table, prefix, identifier, name_field in (
        ("source_implementations", "implementation:", "implementation_id", "class_name"),
        ("configured_component_definitions", "definition:", "definition_id", "logical_id"),
    ):
        for row in conn.execute(f"SELECT record_json FROM {table} WHERE run_id=?", (run_id,)):
            record = json.loads(row[0])
            name = record.get(name_field) or "Unnamed component"
            if prefix == "implementation:" and record.get("package_name"):
                name = record["package_name"] + "." + name
            if record.get("component_kind"):
                name = record["component_kind"] + ": " + name
            names[prefix + record[identifier]] = (name, record.get("source_path", "not recorded"))
    lines.extend(["", "PROPOSED COMPONENT OWNERSHIP",
                  "Other legacy consumers show where the same components are used across the workspace.",
                  f"Current assignment rules: shared library at {libraries.shared_library_min_usage} or more distinct operation consumers; common library above {libraries.broad_library_usage_threshold}.",
                  "Each channel-and-operation pair counts once toward sharing thresholds."])
    labels = {library.library_id: ("Common library (common-lib)" if library.library_id == "common-lib" else f"Shared library {index} ({library.library_id})")
              for index, library in enumerate(libraries.libraries, 1)}
    lines.append("Library build order: " + (" -> ".join(labels.get(name, "Unresolved library") for name in libraries.library_build_order) or "None proposed"))
    for library in libraries.libraries:
        dependencies = libraries.library_dependencies.get(library.library_id, [])
        lines.append(labels[library.library_id] + " depends on: " + (", ".join(labels.get(name, "Unresolved library") for name in dependencies) or "No other proposed libraries"))
    for key, assignment in libraries.assignments.items():
        name, path = names.get(key, ("Unresolved component name", "not recorded"))
        details = ["Source: " + path,
                   "Proposed destination: " + (labels.get(assignment, "Shared library") if assignment else "Operation-local code"),
                   f"Distinct operation consumers: {libraries.usage_counts.get(key, 0)}"]
        consumers = set(libraries.consumers.get(key, []))
        details.append("Selected consumers: " + (", ".join(sorted(consumers & selected)) or "None recorded"))
        details.append("Other legacy consumers (outside this migration): " + (", ".join(sorted(consumers - selected)) or "None"))
        if collapsible:
            from agents.migration_planning.collapsible_sections import collapsible_section
            destination = assignment or "Operation-local code"
            lines.append(collapsible_section(name + " — " + destination, details))
        else:
            lines.append("\n- " + name)
            lines.extend("  " + detail for detail in details)
    lines.extend(["", "DEPENDENCY LIMITS", libraries.dependency_analysis,
                  "Library diagnostics: " + ("; ".join(libraries.diagnostics) if libraries.diagnostics else "None reported"),
                  "", "HOW TO RECORD YOUR DECISION",
                  "If the proposal matches your intent, choose Approve a gate for this run, then Resume a migration.",
                  "If the proposal needs changes or more evidence, choose Reject a gate, then address the review findings before continuing.",
                  "Record your decision through the menu. The application binds it to this report's content.",
                  "Machine identifiers and full library data remain in shared_library_plan.json and the run database."])
    return "\n".join(lines)
