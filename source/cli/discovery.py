"""Discover configuration files and current-layout migration runs without mutations."""

from pathlib import Path
import sqlite3

from runtime.workspace_paths import resolve_run_directory


# Checkpoints currently accepted by resume_pipeline; discovery never executes it.
RESUMABLE_PHASES = {
    "conversion_plan_pending", "conversion_plan_rejected", "conversion_plan_approved", "conversion_plan_blocked",
    "planning_inputs_ready", "planning", "planning_failed", "gate_1_pending",
    "gate_1_rejected", "closures_blocked", "conversion_pending", "component_review",
    "component_revision", "component_review_blocked", "gate_2_pending", "gate_2_rejected",
    "assembly_pending", "operation_assembly", "assembly_blocked", "operation_review_pending",
    "operation_review", "operation_revision", "operation_review_blocked", "gate_3_pending",
    "gate_3_rejected", "service_generation_pending", "service_generation",
    "service_generation_blocked", "validation_evidence_pending", "component_correction_pending",
    "assembly_correction_pending", "gate_4_pending", "gate_4_rejected", "finalization_blocked",
    "migration_approved", "dry_run_complete",
    "conversion_service_connections_pending",
    "operation_pending", "operation_workflow_completed", "operation_publication_pending",
}


def discover_configurations(root: Path) -> list[Path]:
    """Return YAML files within the project's config and configs folders."""
    return sorted({path for name in ("config", "configs")
                   for path in (root / name).rglob("*")
                   if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}})


def discover_runs(output_root: str, *, resumable_only: bool = False) -> list[tuple[str, str]]:
    """Read valid current-layout run identities and labels without creating databases."""
    root = Path(output_root)
    if not root.is_dir():
        return []
    runs = []
    for directory in sorted(root.iterdir()):
        try:
            resolve_run_directory(output_root, directory.name)
        except ValueError:
            continue
        database = directory / "state" / "migration.db"
        if not database.is_file() or not (directory / "state" / "profile.json").is_file():
            continue
        try:
            with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
                row = conn.execute("SELECT run_id, status, current_phase FROM runs WHERE run_id=?",
                                   (directory.name,)).fetchone()
            if row and (not resumable_only or row[2] in RESUMABLE_PHASES):
                runs.append((row[0], f"{row[0]} — {row[1]} — {row[2] or 'No checkpoint'}"))
        except sqlite3.Error:
            continue
    return runs
