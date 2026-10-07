SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        run_mode TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'started',
        current_phase TEXT,
        run_config_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        schema_version TEXT NOT NULL DEFAULT 'v1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_tasks (
        task_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        scope_type TEXT NOT NULL,
        scope_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        target_language TEXT NOT NULL DEFAULT 'any',
        schema_version_key TEXT NOT NULL DEFAULT 'v1',
        status TEXT NOT NULL DEFAULT 'pending',
        blocking_reason TEXT,
        attempt_number INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        input_json TEXT,
        output_json TEXT,
        error_message TEXT,
        started_at TEXT,
        completed_at TEXT,
        heartbeat_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_artifacts (
        artifact_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        logical_id TEXT NOT NULL,
        source_path TEXT,
        source_hash TEXT,
        channel TEXT,
        shared INTEGER NOT NULL DEFAULT 0,
        used_by_count INTEGER NOT NULL DEFAULT 0,
        used_by_ids_json TEXT,
        metadata_json TEXT,
        conversion_status TEXT NOT NULL DEFAULT 'not_started',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS channel_operations (
        operation_name TEXT NOT NULL,
        channel TEXT NOT NULL,
        xml_file_path TEXT NOT NULL,
        run_id TEXT NOT NULL,
        PRIMARY KEY (operation_name, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operations (
        operation_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        xml_file_path TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (operation_id, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tag_registry (
        tag_name TEXT NOT NULL,
        fqcn TEXT NOT NULL,
        channel TEXT,
        source_dse_ini TEXT,
        run_id TEXT NOT NULL,
        PRIMARY KEY (tag_name, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS native_java_artifacts (
        artifact_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        conversion_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        logical_id TEXT NOT NULL,
        source_hash TEXT,
        invalidation_event_id TEXT,
        artifact_path TEXT,
        compiles INTEGER NOT NULL DEFAULT 0,
        review_status TEXT NOT NULL DEFAULT 'pending',
        review_notes_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        blocking_reason TEXT,
        attempt_number INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS generated_artifacts (
        artifact_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        operation_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        target_language TEXT NOT NULL,
        artifact_kind TEXT NOT NULL,
        source_hash TEXT,
        invalidation_event_id TEXT,
        artifact_schema_version TEXT NOT NULL DEFAULT 'v1',
        generated_path TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        blocking_reason TEXT,
        attempt_number INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS component_registry (
        component_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        artifact_kind TEXT NOT NULL,
        logical_id TEXT NOT NULL,
        source_hash TEXT,
        target_language TEXT NOT NULL DEFAULT 'any',
        artifact_schema_version TEXT NOT NULL DEFAULT 'v1',
        generated_path TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        used_by_operations_json TEXT,
        used_by_validated_operations INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS service_layer_requirements (
        format_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        requirements_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (format_id, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operation_closures (
        operation_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'BLOCKED_UNRESOLVED_REFERENCE',
        closure_json TEXT,
        blocking_issues_json TEXT,
        source_hash_composite TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (operation_id, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS routing_plans (
        operation_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        plan_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (operation_id, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS context_plans (
        operation_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        plan_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (operation_id, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS serialization_plans (
        operation_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        plan_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (operation_id, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS context_hierarchies (
        context_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        chain_json TEXT NOT NULL,
        root_id TEXT NOT NULL,
        has_cycle INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        PRIMARY KEY (context_id, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS context_field_inventories (
        context_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        full_chain_json TEXT,
        inventory_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (context_id, channel, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invalidation_events (
        event_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        corrected_artifact_id TEXT NOT NULL,
        corrected_artifact_kind TEXT NOT NULL,
        change_reason TEXT NOT NULL,
        old_hash TEXT,
        new_hash TEXT,
        affected_operation_ids_json TEXT,
        affected_artifact_ids_json TEXT,
        created_at TEXT NOT NULL,
        schema_version TEXT NOT NULL DEFAULT 'v1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execution_traces (
        trace_id TEXT PRIMARY KEY,
        operation_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        target TEXT NOT NULL,
        scenario TEXT NOT NULL,
        target_language TEXT,
        trace_json TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trace_comparisons (
        comparison_id TEXT PRIMARY KEY,
        operation_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        run_id TEXT NOT NULL,
        scenario TEXT NOT NULL,
        matched INTEGER NOT NULL DEFAULT 0,
        step_sequence_match INTEGER,
        rc_per_step_match INTEGER,
        context_writes_match INTEGER,
        reply_format_match INTEGER,
        final_xml_match INTEGER,
        failure_class TEXT,
        comparison_json TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS migration_plans (
        plan_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        plan_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS process_locks (
        task_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        process_id TEXT NOT NULL,
        hostname TEXT NOT NULL,
        started_at TEXT NOT NULL,
        heartbeat_at TEXT NOT NULL
    )
    """,
]

from tools.state_store_tools.component_inventory import INVENTORY_SCHEMA

SCHEMA_STATEMENTS.extend(INVENTORY_SCHEMA)
SCHEMA_STATEMENTS.append("CREATE TABLE IF NOT EXISTS shared_library_plans (run_id TEXT PRIMARY KEY, plan_json TEXT NOT NULL)")
SCHEMA_STATEMENTS.append("""CREATE TABLE IF NOT EXISTS managed_component_registry (
    component_id TEXT PRIMARY KEY, source_key TEXT NOT NULL, input_hash TEXT NOT NULL,
    task_id TEXT NOT NULL, record_json TEXT NOT NULL)""")
