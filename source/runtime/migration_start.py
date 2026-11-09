"""Continue full native migrations after successful intake without bypassing approval gates."""

import sqlite3
from runtime.workspace_paths import run_database_path


def continue_after_intake(profile, directory):
    """Use the normal resume entry point only for an inventory-ready full-conversion profile."""
    if getattr(profile, 'conversion_strategy', None) != 'behavior_units' or getattr(profile, 'scoped_native_mode', 'prepare') not in {'component_first_v1', 'behavior_units_v1'}:
        return directory
    with sqlite3.connect(run_database_path(directory)) as conn:
        row = conn.execute('SELECT status,current_phase FROM runs WHERE run_id=?', (directory.name,)).fetchone()
    if row != ('paused', 'scoped_inventory_ready'):
        return directory
    from runtime.checkpoints import resume_pipeline
    return resume_pipeline(str(directory.parent), directory.name)
