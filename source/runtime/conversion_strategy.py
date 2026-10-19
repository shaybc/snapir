"""Dispatch the opt-in configured behavior pipeline without changing legacy runs."""


def resume_behavior_strategy(conn, config, profile, directory):
    """Continue option two through the existing seven stages and four gates."""
    from tools.state_store_tools.runs import get_run
    run = get_run(conn, config.run_id)
    if run["current_phase"] in {"gate_4_pending", "gate_4_rejected", "finalization_blocked", "migration_approved", "dry_run_complete"}:
        from models.migration_models import MigrationPlan
        from runtime.finalization import run_finalization
        row = conn.execute("SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1", (config.run_id,)).fetchone()
        if row is None:
            raise ValueError("Finalization requires a persisted native migration plan")
        run_finalization(conn, config, profile, MigrationPlan.model_validate_json(row[0]), directory)
        return directory
    from runtime.behavior_conversion.runner import resume_behavior_pipeline
    return resume_behavior_pipeline(conn, config, profile, directory)
