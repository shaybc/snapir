# Prompt 31 — Full Batch Scale + Batch Dispatcher

## Context
Stage 8. All agents from Prompts 01-30 exist and have been tested on pilot batch.
This prompt adds the batch dispatcher that scales from 3-5 pilot operations to
the full channel operation set.

## Reference
`Implementation_plan_V8.md` section 15 Stage 8.

## Files to create
```
tools/routing_tools/batch_dispatcher.py
tools/routing_tools/batch_progress_tracker.py
```

## `batch_dispatcher.py`

```python
def dispatch_batch(
    conn,
    batch: MigrationBatch,
    run_config: RunConfig,
    on_operation_complete: Callable,
    on_operation_failed: Callable
) -> BatchResult:
    """
    Processes all operations in a batch through Phases 2-6.
    Uses MAX_PARALLEL_CONVERSION_WORKERS for Phase 3 (conversion).
    Uses MAX_PARALLEL_LLM_TASKS for LLM operations.
    Uses MAX_PARALLEL_BUILD_TASKS for compile operations.

    For each operation in batch:
    1. Build closure (Phase 2) — sequential per operation.
    2. Convert artifacts (Phase 3) — parallel up to MAX_PARALLEL_CONVERSION_WORKERS.
       Reuse from registry if hash matches.
    3. Assemble (Phase 4) — sequential per operation (plans depend on converted artifacts).
    4. Generate (Phase 5) — parallel up to MAX_PARALLEL_BUILD_TASKS.
    5. Validate (Phase 6) — parallel up to MAX_PARALLEL_BUILD_TASKS.

    Calls on_operation_complete(operation_id) after each fully validated operation.
    Calls on_operation_failed(operation_id, blocking_reason) on block.

    Between operations: sleep INTER_BATCH_DELAY_SECS.
    Returns BatchResult with counts.
    """

def dispatch_all_batches(
    conn,
    plan: MigrationPlan,
    run_config: RunConfig
) -> RunResult:
    """
    Dispatches all batches in plan order.
    After each batch: check for promotable shared artifacts and run common-lib build.
    Returns RunResult with per-batch summaries.
    """
```

## `batch_progress_tracker.py`

```python
def update_progress(conn, run_id: str, batch_id: str, operation_id: str,
                    status: str) -> None: ...

def get_batch_progress(conn, run_id: str, batch_id: str) -> dict: ...

def print_progress_bar(conn, run_id: str) -> None:
    """Prints a terminal progress bar: [=====>    ] 47/247 operations"""
```

## INTER_BATCH_DELAY_SECS
After every batch completes: sleep INTER_BATCH_DELAY_SECS before starting next.
This prevents resource spikes when running many batches sequentially.

## Tests
`tests/test_batch_dispatcher.py`:
- dispatch_batch respects MAX_PARALLEL_CONVERSION_WORKERS limit.
- Blocked operation in batch does not prevent other operations from completing.
- Progress bar shows correct fraction after each completion.
- Common-lib rebuild triggered after batch with new shared promotions.
