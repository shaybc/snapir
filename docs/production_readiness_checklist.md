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
- [ ] Review needs_human_review operations - handle or explicitly exclude
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
