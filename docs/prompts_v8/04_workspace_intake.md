# Prompt 04 — `workspace_intake.py` + `constants.py` + routing tools

## Context
Stage 2, Step 4. Models, state_store, and artifact_registry exist.
This is the pipeline entry point — the operator runs this script to start a run.

## Reference
`Implementation_plan_V8.md` sections 3 (RunConfig), 5 Phase 0, 13 (constants).

## Files to create

```
workspace_intake.py           ← project root (entry point)
constants.py                  ← project root (defaults)
tools/workspace_intake_tools/
├── __init__.py
├── env_loader.py             ← reads .env, applies constants.py fallbacks
├── vault_validator.py        ← checks vault structure
├── channel_validator.py      ← checks target channel in registry
├── db_initializer.py         ← creates tables, reconcile_on_startup
└── run_factory.py            ← builds and persists RunConfig
tools/routing_tools/
├── __init__.py
└── target_runtime_router.py  ← routes to language-specific agents
```

## `constants.py`
Implement exactly as specified in plan section 13. All values listed in the
`.env` to `constants.py` mapping table must be present with the correct defaults.

## `env_loader.py`
```python
def load_env_with_fallbacks(env_file: str | None = None) -> dict:
    """
    1. Reads .env file (python-dotenv).
    2. For every key in constants.py: if absent from .env, use constants value.
    3. Parses comma-separated list values: TARGET_CHANNELS, TARGET_LANGUAGES,
       INCLUDE_OPERATIONS, EXCLUDE_OPERATIONS, FORBIDDEN_DEPENDENCIES.
    4. Returns fully resolved config dict.
    """
```

## `channel_validator.py`
```python
def validate_channel_in_registry(
    vault_root: str,
    target_channels: list[str]
) -> list[str]:
    """
    Reads analysis/channel-operation-registry.md.
    Returns list of channels NOT found in registry.
    Empty list = all channels valid.
    """
```

## `run_factory.py`
```python
def create_run_config(resolved_env: dict, run_id: str) -> RunConfig:
    """Builds RunConfig from resolved env dict. Validates all required fields."""

def persist_run_config(conn, config: RunConfig) -> None:
    """Writes to runs table and run_config.json under output_root."""
```

## `workspace_intake.py` — main entry point

Implements all 14 validation steps from plan section 5 Phase 0, in order:
1. composer_root exists and contains XML files
2. run_mode is valid
3. single_channel has exactly one target_channel
4. multi_channel has one or more target_channels
5. full_inventory does not require a target channel
6. every target_language is supported
7. composer-mapper runs successfully (invoked as subprocess)
8. vault_root exists with required subdirectories
9. analysis/channel-operation-registry.md exists
10. target channels present in registry (for modes that require it)
11. model endpoint reachable (warning only, logged, not blocking)
12. git state (if ENABLE_GIT=true)
13. DB: create tables, reconcile_on_startup
14. Prior run resume or new run

After all blocking checks pass:
- Write RunConfig to file + DB
- Log summary: run_id, mode, channels, languages, operation counts
- Start `RootMigrationOrchestratorAgent`

```
python workspace_intake.py [--env .env] [--resume run_id]
```

Exit code 0 on success, 1 on any blocking validation failure.
Print clear human-readable error for every blocking failure before exit.

## `target_runtime_router.py`
```python
def route_to_target_agents(
    target_languages: list[str],
    operation_id: str,
    channel: str
) -> list[str]:
    """
    Returns list of agent names to invoke for each target language.
    java   -> JavaServiceGenerationAgent
    nodejs -> NodejsServiceGenerationAgent
    python -> PythonServiceGenerationAgent
    """
```

## Rules
- composer-mapper is invoked as `subprocess.run(["java", "-jar", ...])`.
- All validation errors accumulate before exit — report all failures at once,
  not just the first.
- `--resume run_id` skips DB initialization and reloads the existing RunConfig.
- `INCLUDE_OPERATIONS` / `EXCLUDE_OPERATIONS` are loaded here and stored in RunConfig.

## Tests
`tests/test_workspace_intake.py`:
- Missing COMPOSER_ROOT fails with clear error.
- multi_channel with no TARGET_CHANNELS fails.
- Unknown TARGET_LANGUAGE fails.
- Target channel not in registry fails.
- Valid .env produces correct RunConfig with include_operations=None by default.
- INCLUDE_OPERATIONS=A,B parses to ["A","B"].
- EXCLUDE_OPERATIONS=C parses to ["C"].
