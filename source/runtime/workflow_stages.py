"""Use the README workflow vocabulary for report locations and progress labels."""

STAGES = {
    "intake_and_legacy_analysis": "Intake and legacy analysis",
    "migration_planning": "Migration planning",
    "dependency_closure_and_component_conversion": "Dependency closure and component conversion",
    "component_review": "Component review",
    "operation_assembly_and_review": "Operation assembly and review",
    "service_generation_and_validation": "Service generation and validation",
    "final_validation": "Final validation",
}

REPORT_FOLDERS = {stage: f"{index}_{stage}" for index, stage in enumerate(STAGES, 1)}

REPORT_STAGES = {
    **{name: "intake_and_legacy_analysis" for name in (
        "run_config.json", "java_source_index.json", "java_classpath_index.json", "component_inventory.json",
        "java_source_dependencies.json", "component_usage.json", "configured_component_usage.json")},
    **{name: "migration_planning" for name in ("planning_inputs.json", "shared_library_plan.json", "gate_1_report.md", "gate_1_report.txt")},
    **{name: "dependency_closure_and_component_conversion" for name in ("dependency_closure.json", "closures.json", "managed_conversion_results.json")},
    "gate_2_report.txt": "component_review",
    **{name: "operation_assembly_and_review" for name in ("assembly_results.json", "gate_3_report.txt")},
    "service_validation_results.json": "service_generation_and_validation",
    **{name: "final_validation" for name in ("delivery_manifest.json", "final_report.md", "gate_4_report.txt")},
}


def workflow_stage(phase):
    """Map detailed persisted checkpoints to their containing workflow stage."""
    phase = phase or ""
    if phase.startswith(("gate_4", "finalization")) or phase in {"migration_approved", "dry_run_complete"}:
        return "final_validation"
    if phase.startswith("service_generation") or phase == "validation_evidence_pending":
        return "service_generation_and_validation"
    if phase.startswith(("operation_", "assembly_", "gate_3")):
        return "operation_assembly_and_review"
    if phase.startswith(("component_review", "component_revision", "gate_2")):
        return "component_review"
    if phase.startswith(("closure", "dependency_closure", "conversion_", "component_correction")):
        return "dependency_closure_and_component_conversion"
    if phase.startswith(("planning", "gate_1")):
        return "migration_planning"
    return "intake_and_legacy_analysis"


def workflow_stage_label(phase):
    """Return the human-facing stage name for a checkpoint."""
    return STAGES[workflow_stage(phase)]
