# Prompt 13 — `OperationClosureBuilderTool` + `ClosureValidatorTool`

## Context
Stage 2, Step 10. All conversion tools from Prompts 10-12 exist.
Context hierarchies and field inventories are pre-built (Prompts 07, 11).
This is the most important deterministic step in the pipeline.

## Reference
`Implementation_plan_V8.md` section 5 Phase 2 — read the entire phase carefully.
The ClosureValidatorTool 10-check table is the authoritative spec.

## Files to create
```
tools/conversion_tools/closure_builder_tool.py
tools/conversion_tools/closure_validator_tool.py
```

## `closure_builder_tool.py`

```python
def build_operation_closure(
    conn,
    operation_id: str,
    channel: str,
    run_id: str,
    composer_root: str,
    vault_root: str
) -> OperationClosure:
    """
    Orchestrates all sub-tools to build a complete OperationClosure.

    Step 1: Load operation metadata from source_artifacts.
      - source_xml_path, operation_fields, ini_values, host_key, ref_formats,
        return_body_switches (from opStep vault notes aggregated).

    Step 2: ChannelFilterTool
      Call filter_opsteps_for_channel(conn, operation_id, channel, run_id).
      -> included_opstep_ids, excluded_opsteps.

    Step 3: JavaImplResolverTool
      Call resolve_java_impls(conn, included_opstep_ids, run_id, composer_root).
      -> java_classes list, blocking_issues from this step.

    Step 4: FormatDependencyResolverTool
      Collect all format_ids from ref_formats values.
      Call resolve_format_dependencies(conn, format_ids, run_id, vault_root).
      -> FormatSet, blocking_issues from this step.

    Step 5: ContextHierarchyResolverTool (read pre-built)
      Call get_context_hierarchy(conn, operation_context_id, run_id).
      -> context_chain.

    Step 6: ContextFieldResolverTool (read pre-built)
      Call get_accessible_fields(conn, operation_context_id, run_id).
      -> context_fields.

    Step 7: Build routing_graph from included_opstep_ids.
      For each opStep: read transitions from metadata_json.
      Resolve step names to step_ids (validate all targets exist in included list
      or are terminal: "end", "next").
      -> routing_graph dict.

    Step 8: Aggregate return_body_switches across all included opSteps.

    Step 9: Identify shared_formats and shared_java_classes.

    Step 10: Compute source_hash_composite from all contributing source_hashes.
      SHA-256 of the concatenated sorted list of source_hash values.

    Step 11: Assemble and store OperationClosure.
      If any blocking_issues: set appropriate ClosureStatus.
      Call ClosureValidatorTool.
      Store in operation_closures table.

    Return the assembled OperationClosure.
    """

def build_closures_for_batch(
    conn,
    operation_ids: list[str],
    channel: str,
    run_id: str,
    composer_root: str,
    vault_root: str
) -> list[OperationClosure]:
    """
    Builds closures for all operations in a batch.
    Returns list of closures (READY and BLOCKED).
    Logs summary: READY count, BLOCKED count with breakdown by ClosureStatus.
    """
```

## `closure_validator_tool.py`

Implement all 10 checks exactly as specified in plan section 5 Phase 2:

```python
def validate_closure(
    closure: OperationClosure,
    conn,
    run_id: str,
    composer_root: str
) -> OperationClosure:
    """
    Runs 10 checks. Returns closure with status set.
    Sets closure.status = READY only if ALL 10 checks pass.
    Otherwise sets the most severe blocking status found.

    Check 1: All included_opstep_ids have a JavaClassRef in java_classes.
    Check 2: All JavaClassRef.source_file exist on disk.
    Check 3: All format_ids in formats.all_format_ids exist in source_artifacts.
    Check 4: All formatter_tags in formats.formatter_tags are in tag_registry.
    Check 5: All decorator tags in formats.decorator_chains are in tag_registry.
    Check 6: context_chain terminates at parent=nil (has_cycle=False).
    Check 7: csErrorReplyFormat defined if any opStep has return_body_switches.
    Check 8: formats.unresolved_format_refs is empty.
    Check 9: blocking_issues list is empty.
    Check 10: routing_graph covers all RC values from all JavaClassRef.return_codes.

    Severity order (highest to lowest):
    BLOCKED_MISSING_IMPL_CLASS > BLOCKED_MISSING_FORMAT > BLOCKED_UNKNOWN_TAG >
    BLOCKED_UNRESOLVED_REFERENCE > NEEDS_HUMAN_MAPPING

    For Check 10 (most important):
    For each JavaClassRef, read its return_codes dict.
    For the corresponding opStep's routing_graph entry, check that every RC key
    in return_codes has a corresponding transition rule (on{N}Do or onOtherDo).
    A missing rule is a latent routing gap — it WILL cause wrong behavior in prod.
    Add ClosureBlockingIssue(BLOCKED_UNRESOLVED_REFERENCE,
                             detail="Latent routing gap: RC {N} emitted by {fqcn}
                                     has no routing rule in operation XML").
    """
```

## Rule: NO conversion starts until closure.status == READY

Every Phase 3 agent must call:
```python
def assert_closure_ready(closure: OperationClosure) -> None:
    if closure.status != ClosureStatus.ready:
        raise ClosureNotReadyError(
            f"{closure.operation_id}/{closure.channel}: "
            f"closure status is {closure.status}, "
            f"issues: {closure.blocking_issues}"
        )
```

Expose this function from `closure_validator_tool.py`.

## Tests
`tests/test_closure_builder.py`:
- READY closure: all 10 checks pass, status=READY, blocking_issues=[].
- Check 1 failure: opStep without JavaClassRef → BLOCKED_MISSING_IMPL_CLASS.
- Check 6 failure: context cycle → BLOCKED_UNRESOLVED_REFERENCE.
- Check 7 failure: on4Return without csErrorReplyFormat → BLOCKED_MISSING_FORMAT.
- Check 10 failure: implClass returns RC 8, no on8Do in XML → BLOCKED_UNRESOLVED_REFERENCE
  with "Latent routing gap" in detail.
- `build_closures_for_batch` logs READY/BLOCKED counts.
- assert_closure_ready raises on non-READY status.
