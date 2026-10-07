"""Persist the library ownership plan included in planning approval."""

from models.shared_library_plan import SharedLibraryPlan


def save_shared_library_plan(conn, run_id, plan):
    """Save an ownership snapshot without replacing the operation migration plan."""
    conn.execute("INSERT OR REPLACE INTO shared_library_plans VALUES (?, ?)", (run_id, plan.model_dump_json()))
    conn.commit()


def get_shared_library_plan(conn, run_id):
    """Return the reviewed-plan candidate when the run has a component inventory."""
    row = conn.execute("SELECT plan_json FROM shared_library_plans WHERE run_id=?", (run_id,)).fetchone()
    return SharedLibraryPlan.model_validate_json(row[0]) if row else None
