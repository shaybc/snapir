# Prompt 33 — End-to-End Pilot Test

## Context
Stage 8. All components exist (Prompts 01-32).
This prompt defines the integration test that validates the full pipeline
on a small set of operations before production scale-out.

## Reference
`Implementation_plan_V8.md` section 15 Stage 8.

## Files to create
```
tests/e2e/
├── __init__.py
├── conftest.py
├── fixtures/
│   ├── sample_vault/           ← minimal synthetic vault for testing
│   ├── sample_java_sources/    ← two simple implClasses
│   └── expected_outputs/       ← expected generated files
├── test_pilot_pipeline.py
└── test_invalidation_e2e.py
```

## Synthetic test fixtures

Create a minimal WSBCC fixture with:
- 2 operations: `SimpleGetOp` (one step, linear) and `BranchGetOp` (two steps, branch)
- `SimpleGetOp`: one opStep `GetDataSP` with on0Do=end, on4Do=NotFound
- `BranchGetOp`: two opSteps `ValidateInput` → `GetDetailSP`, with RC branching
- One shared format: `StandardHeaderFmt` (used by both operations)
- One shared context: `BaseCtxt` (parent=nil)
- Two Java implClasses with real (minimal) IBM framework code

## `test_pilot_pipeline.py`

```python
def test_full_pilot_pipeline(tmp_path, mock_llm):
    """
    End-to-end test for the pilot batch (2 operations).

    Steps:
    1. Set up synthetic vault in tmp_path.
    2. Run workspace_intake (with mock composer-mapper).
    3. Run LegacyComposerAnalysisAgent.
    4. Run ContextHierarchyResolverTool.
    5. Run SharedArtifactClassificationPass.
    6. Run MigrationPlanningAgent (mock LLM returns valid plan).
    7. Run OperationClosureBuilderTool for both operations.
       Assert both closures are READY.
    8. Run Phase 3 conversion for all required artifacts.
       Assert IBM imports removed from cleaned classes.
       Assert JAXB DTOs compile.
    9. Run Phase 4 assembly.
       Assert assembled services compile.
       Assert OperationEquivalenceReviewAgent approves both.
    10. Run Phase 5 Java generation.
        Assert mvn compile passes.
    11. Assert StandardHeaderFmt promoted to common-lib
        (used by 2 validated operations).
    12. Check trace scenarios derived correctly for BranchGetOp.
    """

def test_include_operations_filter(tmp_path, mock_llm):
    """
    With INCLUDE_OPERATIONS=SimpleGetOp:
    Only SimpleGetOp appears in operations table.
    BranchGetOp is absent from all downstream processing.
    """

def test_exclude_operations_filter(tmp_path, mock_llm):
    """
    With EXCLUDE_OPERATIONS=BranchGetOp:
    BranchGetOp is absent from operations table.
    SimpleGetOp is processed normally.
    """
```

## `test_invalidation_e2e.py`

```python
def test_shared_implclass_invalidation(tmp_path, mock_llm):
    """
    1. Complete a full run for SimpleGetOp.
    2. Modify the source hash of GetDataSP implClass in the vault.
    3. Re-run LegacyComposerAnalysisAgent (re-import vault).
    4. Assert detect_hash_changes finds GetDataSP changed.
    5. Assert cascade_invalidation marks SimpleGetOp native_java as needs_rerun.
    6. Assert BranchGetOp (which doesn't use GetDataSP) is NOT marked.
    """

def test_closure_blocking_latent_routing_gap(tmp_path):
    """
    Create an implClass whose return_codes includes RC=8.
    Create an operation XML with no on8Do for that opStep.
    Run OperationClosureBuilderTool.
    Assert closure.status = BLOCKED_UNRESOLVED_REFERENCE.
    Assert blocking_issues contains 'Latent routing gap'.
    """
```

## Mock LLM
All LLM calls use a `mock_llm` fixture that returns pre-written valid responses
for each expected prompt pattern. The responses are stored in
`tests/e2e/fixtures/mock_llm_responses/` as JSON files keyed by prompt hash.

## Running the tests
```bash
pytest tests/e2e/ -v --timeout=120
```
All e2e tests must pass before the pilot is considered ready for scale-out.
