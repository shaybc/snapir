# Prompt 34 — Production Readiness Checklist + `health_check.py`

## Context
Final prompt. All components exist (Prompts 01-33) and e2e tests pass.
This prompt adds the operational health check script and the production
readiness checklist that must pass before migrating the full operation set.

## Reference
`Implementation_plan_V8.md` section 15 Stage 8.

## Files to create
```
health_check.py          ← project root
docs/production_readiness_checklist.md
```

## `health_check.py`

A standalone diagnostic script. Run before any migration run to verify the
environment is correctly configured.

```python
"""
Usage: python health_check.py [--env .env]

Checks:
1. Python version >= 3.11
2. ADK installed and importable
3. All required pip packages installed (from requirements.txt)
4. Java 17+ available (java -version)
5. Maven 3.8+ available (mvn -version)
6. composer-mapper JAR exists and runs (java -jar composer-mapper.jar --help)
7. COMPOSER_ROOT exists and is readable
8. VAULT_ROOT exists (or can be created)
9. OUTPUT_ROOT is writable
10. DB_PATH directory is writable
11. LiteLLM proxy reachable: POST {LITELLM_BASE_URL}/v1/chat/completions
    with a minimal test prompt (1 token)
12. LEGACY_SERVICE_BASE_URL reachable (if set, warning only if not)
13. SQLite write/read test in DB_PATH
14. FORBIDDEN_DEPENDENCIES list is not empty

Prints PASS/FAIL for each check.
Exits 0 if all blocking checks pass.
Exits 1 if any blocking check fails.
Checks 12 is warning-only (non-blocking).
"""
```

## `docs/production_readiness_checklist.md`

```markdown
# Production Readiness Checklist

Before migrating the full operation set from pilot to production:

## Environment
- [ ] health_check.py passes all blocking checks
- [ ] COMPOSER_ROOT points to the complete WSBCC workspace (all channels)
- [ ] VAULT_ROOT contains vault generated with correct --channel flag
- [ ] Legacy WSBCC system accessible at LEGACY_SERVICE_BASE_URL

## Pilot validation
- [ ] All pilot batch operations (3-5) reach status=validated
- [ ] No routing_mismatch failures remain unresolved
- [ ] All trace scenarios pass for pilot operations
- [ ] common-lib builds cleanly with all shared artifacts promoted
- [ ] IBM dependency guard finds zero violations
- [ ] Human Gate 3 approved

## Configuration
- [ ] TARGET_CHANNELS set to the correct channel(s) for this run
- [ ] MAX_OPERATIONS_PER_BATCH set appropriately (start with 5)
- [ ] INCLUDE_OPERATIONS / EXCLUDE_OPERATIONS set if any filtering needed
- [ ] GOLDEN_TESTS_ROOT contains at least one golden pair per pilot operation

## Before scale-out
- [ ] Backup migration.db from pilot run
- [ ] Review unresolved references in analysis/unresolved-references.md
- [ ] Review needs_human_review operations — handle or explicitly exclude
- [ ] Confirm legacy system performance under trace capture load
- [ ] Review performance benchmarks from pilot (p50/p95 acceptable?)

## After each batch
- [ ] Check batch progress in DB (batch_progress_tracker)
- [ ] Review any new routing_mismatch or conversion_gap failures
- [ ] Confirm common-lib promotions with each batch
- [ ] Run health_check.py before each batch if run spans multiple days

## Final
- [ ] All operations reach status=validated or status=needs_human_review (documented)
- [ ] Human Gate 4 approved
- [ ] Final migration report generated and reviewed
- [ ] Generated services deployed to non-production OpenShift environment for smoke test
```

## Tests
`tests/test_health_check.py`:
- All checks pass with correct mock environment.
- Missing Java returns non-zero exit.
- Unreachable LiteLLM proxy returns warning (non-zero exit only if blocking).
```
