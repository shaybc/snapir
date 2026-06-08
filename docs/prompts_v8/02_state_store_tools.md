# Prompt 02 — `state_store_tools/`

## Context
Stage 1, Step 2. Models from Prompt 01 exist. Nothing else is built yet.
This module owns every SQLite table and every read/write function used by the
entire pipeline. All other components import from here — never write raw SQL
outside this package.

## Reference
`Implementation_plan_V8.md` sections 5, 9, 10, 11 (DB tables).

## Package structure

```
tools/state_store_tools/
├── __init__.py
├── schema.py          ← CREATE TABLE statements only
├── db.py              ← connection factory, migrations, reconcile_on_startup
├── runs.py            ← runs table CRUD
├── agent_tasks.py     ← agent_tasks table CRUD
├── source_artifacts.py
├── channel_operations.py
├── tag_registry.py
├── native_java_artifacts.py
├── generated_artifacts.py
├── operation_closures.py
├── routing_plans.py
├── context_plans.py
├── serialization_plans.py
├── context_hierarchies.py
├── context_field_inventories.py
├── service_layer_requirements.py
├── invalidation_events.py
├── invalidation.py    ← detect_hash_changes, cascade_invalidation (Rules 1-5)
├── execution_traces.py
├── trace_comparisons.py
└── process_locks.py
```

## Schema — every table exactly as specified in the plan

### `runs`
```sql
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    run_mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    current_phase TEXT,
    run_config_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 'v1'
);
```

### `agent_tasks`
```sql
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
);
```

### `source_artifacts`
```sql
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
);
```

### `channel_operations`, `tag_registry`, `operations` — as specified in plan section 11

### `native_java_artifacts`
```sql
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
);
```

### `generated_artifacts`
```sql
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
);
```

### Plan-defined tables
Include all tables from plan section 11:
`operation_closures`, `routing_plans`, `context_plans`, `serialization_plans`,
`context_hierarchies`, `context_field_inventories`, `service_layer_requirements`

### Trace tables (from plan section 6):
`execution_traces`, `trace_comparisons`

### Invalidation:
`invalidation_events` (from plan section 10)

### `process_locks`
```sql
CREATE TABLE IF NOT EXISTS process_locks (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    process_id TEXT NOT NULL,
    hostname TEXT NOT NULL,
    started_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL
);
```

### `component_registry`
```sql
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
);
```

## `db.py` — connection factory and lifecycle

```python
def get_connection(db_path: str) -> sqlite3.Connection:
    """Returns a WAL-mode connection with row_factory=sqlite3.Row."""

def create_all_tables(conn: sqlite3.Connection) -> None:
    """Executes all CREATE TABLE IF NOT EXISTS statements from schema.py."""

def reconcile_on_startup(conn: sqlite3.Connection, run_id: str) -> None:
    """
    On startup, find any agent_tasks with status='started' or
    process_locks with heartbeat_at older than RUNNER_HEARTBEAT_TIMEOUT_SECONDS.
    Mark those tasks needs_rerun. Remove stale process locks.
    """
```

## `invalidation.py` — cascade rules exactly as in plan section 10

Implement all five rules as described. Each cascade must:
1. Execute as a single DB transaction.
2. Mark all downstream records `needs_rerun`.
3. Create one `InvalidationEvent` per changed artifact (not per downstream).
4. Return an `InvalidationSummary` with counts.

```python
def detect_hash_changes(conn, run_id: str) -> list[HashChange]: ...
def cascade_invalidation(conn, run_id: str,
                         changes: list[HashChange]) -> InvalidationSummary: ...
def _rule1_shared_impl_class(conn, change, run_id): ...
def _rule2_shared_format(conn, change, run_id): ...
def _rule3_operation_xml(conn, change, run_id): ...
def _rule4_context(conn, change, run_id): ...
def _rule5_local_artifact(conn, change, run_id): ...
```

## Task key format
All task keys follow exactly:
```
{run_id}:{agent_name}:{scope_type}:{scope_id}:{channel}:{target_language}:{schema_version}
```
Implement `make_task_key(run_id, agent_name, scope_type, scope_id, channel,
target_language, schema_version="v1") -> str` in `agent_tasks.py`.

## Process lock pattern
Implement acquire/release/heartbeat/is_stale in `process_locks.py`.
Timeout constant from `constants.RUNNER_HEARTBEAT_TIMEOUT_SECONDS`.

## Rules
- No raw SQL outside this package.
- All functions accept `conn: sqlite3.Connection` as first argument.
- All writes use parameterised queries — no f-string SQL.
- All `created_at` / `updated_at` use ISO-8601 UTC strings.
- `updated_at` is set on every write.
- All JSON columns serialise/deserialise via `json.dumps` / `json.loads`.

## Tests
`tests/test_state_store.py`:
- Schema creation is idempotent (run twice, no error).
- `reconcile_on_startup` resets stale `started` tasks to `needs_rerun`.
- `make_task_key` produces the correct format.
- Each of the five invalidation rules marks the correct set of records.
- Hash mismatch with `auto_rerun_impacted_operations=False` creates
  InvalidationEvent but does not set `needs_rerun` (paused state).
