# Prompt 06 — `LegacyComposerAnalysisAgent`

## Context
Stage 2, Step 6. All tools from steps 1-5 exist.
This is the first ADK agent in the pipeline. It orchestrates vault import,
hash-change detection, and invalidation cascade.

## Reference
`Implementation_plan_V8.md` sections 5 Phase 1, 6 (Agent Roster).

## File to create
```
agents/legacy_composer_analysis/
├── __init__.py
└── agent.py
```

## Agent definition

```python
from google.adk.agents import SequentialAgent

legacy_composer_analysis_agent = SequentialAgent(
    name="LegacyComposerAnalysisAgent",
    description="Reads the composer-mapper vault and populates the DB.",
    sub_agents=[...],  # ordered steps below
)
```

## Steps (implemented as tool calls inside a SequentialAgent)

### Step 1 — Import vault
Call `vault_importer.import_vault(conn, vault_root, run_config)`.
Write import summary to `agent_tasks` with status=completed.
If import raises, set status=failed with error_message and re-raise.

### Step 2 — Detect hash changes
Call `detect_hash_changes(conn, run_id)`.
Log count of changes found.

### Step 3 — Cascade invalidation
Call `cascade_invalidation(conn, run_id, changes)`.
Log InvalidationSummary (changed, stale_conversions, stale_operations, stale_services).
If `auto_rerun_impacted_operations=False` and any changes found: set run status
to `paused_awaiting_operator` and emit a human-readable impact report. Do not
continue to next steps.

### Step 4 — Set INVENTORY_COMPLETE
Write checkpoint `INVENTORY_COMPLETE=true` to runs table.
This is a precondition checked by ContextHierarchyResolverTool and
SharedArtifactClassificationPass.

## Rules
- This agent does not call any LLM.
- It does not re-scan WSBCC source files.
- It does not read dse.ini.
- It reads only from the vault_root and writes only to the DB.
- All four steps execute in order; if any step fails, the agent fails.

## Tests
`tests/test_legacy_composer_analysis_agent.py`:
- Successful import sets INVENTORY_COMPLETE.
- Hash change with auto_rerun=False sets run to paused state.
- Import failure sets agent_tasks status=failed.
