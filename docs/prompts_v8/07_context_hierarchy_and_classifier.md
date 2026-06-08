# Prompt 07 — `ContextHierarchyResolverTool` + `SharedArtifactClassificationPass`

## Context
Stage 2, Step 7-8. LegacyComposerAnalysisAgent (06) must have run and set
INVENTORY_COMPLETE before either tool runs.

## Reference
`Implementation_plan_V8.md` sections 5 Phase 1 (tool definitions),
11 (context_hierarchy_resolver_tool).

## Files to create
```
tools/conversion_tools/context_hierarchy_resolver_tool.py
tools/shared_artifact_classifier_tools/
├── __init__.py
└── classifier.py
```

## `context_hierarchy_resolver_tool.py`

Implement exactly as specified in plan section 11:

```python
def build_all_context_hierarchies(conn, run_id: str) -> list[ContextHierarchy]:
    """
    Precondition: INVENTORY_COMPLETE must be set for run_id.
    For every context in source_artifacts WHERE run_id=run_id AND kind='context':
      1. Read parent from metadata_json.
      2. Follow parent links recursively until parent='nil' or parent not found.
      3. If a context_id repeats in the chain: set has_cycle=True, stop.
      4. Store ContextHierarchy in context_hierarchies table.
    Returns list of all built hierarchies.
    Contexts with has_cycle=True are also written to agent_tasks as
    needs_human_review with blocking_reason=context_cycle.
    """

def get_context_hierarchy(conn, context_id: str, run_id: str) -> ContextHierarchy:
    """
    Reads from context_hierarchies table.
    Raises if not found — callers must ensure build_all_context_hierarchies
    was called before invoking this.
    """
```

### Cycle detection rule
Use a seen-set while traversing: if `current_id in seen`, a cycle exists.
Record the full partial chain up to (but not including) the second occurrence
of the repeated id, then set `has_cycle=True`.

## `classifier.py` — SharedArtifactClassificationPass

```python
def run_shared_artifact_classification(conn, run_id: str) -> ClassificationSummary:
    """
    Precondition: INVENTORY_COMPLETE must be set.

    For each source_artifact in this run:
      - If kind=format and used_by_count > 1: mark shared=True
      - If kind=java_class and used_by_count > 1: mark shared=True
      - If kind=context and used_by_count > 1: mark shared=True (for common-lib)
      - Identify 'XML contract candidates': formats with name matching
        standard header/error patterns (e.g. ends with 'HeaderFmt', 'ErrorFmt',
        'StandardError') — flag in metadata_json.

    Updates source_artifacts.shared column.
    Returns ClassificationSummary with counts.
    """
```

`ClassificationSummary` fields: shared_formats, shared_classes, shared_contexts,
xml_contract_candidates, total_processed.

## Rules
- Both tools check INVENTORY_COMPLETE and raise `PreconditionError` if not set.
- `build_all_context_hierarchies` is called BEFORE SharedArtifactClassificationPass.
- Neither tool calls any LLM.
- Context cycles are flagged for human review but do not fail the overall run —
  they simply block the affected operations from entering Phase 2.

## Tests
`tests/test_context_hierarchy.py`:
- Flat context (parent=nil): chain=[context_id], root_id=context_id.
- Two-level chain: chain=[child, parent], root_id=parent.
- Three-level chain: chain=[child, parent, grandparent].
- Synthetic cycle A→B→C→A: has_cycle=True, partial chain recorded.
- SharedArtifactClassificationPass correctly identifies shared formats and classes.
