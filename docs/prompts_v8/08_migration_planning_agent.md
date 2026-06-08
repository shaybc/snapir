# Prompt 08 — `MigrationPlanningAgent`

## Context
Stage 2, Step 9. SharedArtifactClassificationPass (07) has run.
This LLM agent groups operations into batches by complexity, producing the
`MigrationPlan` that drives all subsequent phases.

## Reference
`Implementation_plan_V8.md` sections 5 Phase 1, 6 (Agent Roster),
8 (migration_models).

## Files to create
```
agents/migration_planning/
├── __init__.py
├── agent.py
└── plan_validator.py
```

## Agent definition

```python
from google.adk.agents import LlmAgent

migration_planning_agent = LlmAgent(
    name="MigrationPlanningAgent",
    description="Groups operations into batches by complexity.",
    model=AGENT_MODEL,
    instruction=PLANNING_INSTRUCTION,
    tools=[get_operations_for_planning, write_migration_plan],
)
```

## LLM instruction (PLANNING_INSTRUCTION)

```
You are a migration planner for the Composer Sunset pipeline.

Your job is to group WSBCC operations into batches for conversion.
You receive a list of operations with their complexity indicators
and must assign each to a group and a batch.

GROUPS (assign exactly one per operation):
- one_step: single opStep, no branching
- multi_step_linear: multiple opSteps, linear routing only
- branch_heavy: 3+ RC branches, complex routing graph
- db_bound: implClass is a stored procedure caller (db_accessor behavior type)
- shared_format_context: shares formats or context with many other operations
- unusual_manual_review: circular context, blocked closure, unusual patterns

BATCHING RULES:
- MAX_OPERATIONS_PER_BATCH = {max_ops_per_batch}
- Pilot batch (batch 1): 3-5 operations maximum. Include at least one from
  each group that is represented in the full set.
- Subsequent batches: up to MAX_OPERATIONS_PER_BATCH operations.
- unusual_manual_review group: always in its own batch, last.
- Prefer operations that share formats/contexts in the same batch to
  maximise common-lib reuse.

OUTPUT FORMAT: JSON matching the MigrationPlan schema.
Return only JSON, no explanation.
```

## Tool: `get_operations_for_planning`
```python
def get_operations_for_planning(conn, run_id: str) -> list[dict]:
    """
    Returns all operations from the operations table for this run.
    Includes: operation_id, channel, step_count (from opSteps),
    branch_count (unique RC values across all opSteps), shared_formats_count,
    shared_classes_count, behavior_types of all implClasses, has_blocked_context.
    """
```

## Tool: `write_migration_plan`
```python
def write_migration_plan(conn, plan: MigrationPlan) -> None:
    """Persists MigrationPlan to migration_plans table."""
```

## `plan_validator.py`
```python
def validate_migration_plan(plan: MigrationPlan, run_config: RunConfig) -> list[str]:
    """
    Returns list of validation errors (empty = valid):
    - Batch 1 size is 3-5
    - No batch exceeds MAX_OPERATIONS_PER_BATCH
    - Every operation from the operations table appears exactly once
    - unusual_manual_review group is in its own batch
    - All operation_ids in the plan exist in the operations table
    """
```

The agent retries (up to MAX_AGENT_TASK_RETRIES) if validation returns errors.
Pass the errors back to the LLM with instruction to fix them.

## Human Gate 1 output
After the plan is written and validated, output the Gate 1 report:
```
=== Human Gate 1 ===
Operations to migrate: {N}
Pilot batch: {batch_1_ids}
Batches planned: {batch_count}
Groups: one_step={N}, branch_heavy={N}, ...
Shared formats: {N}
Blocked (needs_human_review): {N}
INCLUDE_OPERATIONS filter active: {yes/no}
EXCLUDE_OPERATIONS filter active: {yes/no}

Approve pilot batch? (yes/no)
```

## Tests
`tests/test_migration_planning.py`:
- Validator rejects batch 1 with 6 operations.
- Validator rejects plan missing an operation.
- Validator rejects unusual_manual_review in non-final batch.
- Gate 1 report includes INCLUDE/EXCLUDE filter status.
