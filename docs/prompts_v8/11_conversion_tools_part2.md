# Prompt 11 — `conversion_tools/` Part 2: `context_field_resolver_tool.py`

## Context
Stage 3. `context_hierarchy_resolver_tool.py` (Prompt 07) must exist and have
populated `context_hierarchies` table before this tool runs.
This tool traverses the full ancestry chain to assemble the complete field set
for a context.

## Reference
`Implementation_plan_V8.md` section 11 (context_field_resolver_tool),
section 5 Phase 3 (ContextFieldInventory description),
`wsbcc_developer_manual_v2.md` section 5 (context inheritance rules).

## File to create
```
tools/conversion_tools/context_field_resolver_tool.py
```

## Implementation

```python
def resolve_context_fields(
    conn,
    context_id: str,
    channel: str,
    run_id: str,
    composer_root: str
) -> ContextFieldInventory:
    """
    Precondition: context_hierarchies must be populated for this run_id.

    1. Load ContextHierarchy for context_id from DB.
       Raises if has_cycle=True — caller must handle blocked operations.

    2. For EACH context_id in hierarchy.chain (leaf first, root last):
       a. Find all operations in source_artifacts that reference this context level
          (operation metadata_json contains context_id).
       b. For each such operation:
          - Find all formats used by this operation (from ref_formats in metadata).
          - For each format: read the Structure section from the vault note.
            Extract all dataName attributes from formatter tags.
            These are fields written/read by formatters at this context level.
          - Find all opSteps of this operation.
          - For each opStep: read implClass FQCN.
            Read Java source from disk via java_source_reader.
            Call detect_context_access_patterns to find setValueAt/getValueAt calls.
            These are fields written/read by business logic at this context level.
       c. Tag each field with:
          context_level = this context_id in the chain
          inherited = (this context_id != the leaf context_id)

    3. Infer Java types from formatter tag types:
       CCDate -> "LocalDate"
       CCBoolean -> "boolean"
       NumberFormat -> "BigDecimal"
       CCIColl -> "List<Object>"  (generic; assembler will specialise)
       all others -> "String"

    4. Deduplicate by field name:
       If same field name appears at multiple chain levels, the deepest
       (most specific, closest to leaf) definition wins.
       Deepest = lowest index in hierarchy.chain (chain is ordered leaf-first).

    5. Store ContextFieldInventory in context_field_inventories table.
    6. Return ContextFieldInventory.
    """

def get_accessible_fields(
    conn,
    context_id: str,
    run_id: str
) -> list[ContextField]:
    """
    Reads the pre-built ContextFieldInventory from DB.
    Returns the flat field list including inherited fields.
    Convenience wrapper for assembler tools.
    """
```

## Type inference rules

| Formatter tag | Inferred Java type |
|---|---|
| `CCDate` | `LocalDate` |
| `CCBoolean` | `boolean` |
| `NumberFormat` | `BigDecimal` |
| `CCIColl` | `List<Object>` |
| `CCString` | `String` |
| `CCTime` | `String` |
| Any other | `String` |

## Deduplication example
Context chain: [GetClientLinksCtxt, InternetBaseCtxt, BaseOpCtxt]
- GetClientLinksCtxt defines "ClientId" as String
- InternetBaseCtxt also defines "ClientId" (inherited from parent, redefined)
- Result: use GetClientLinksCtxt definition (deepest/first in chain wins)

## Rules
- This tool reads Java sources from disk (via java_analysis_tools) to find
  context field names from setValueAt/getValueAt patterns.
- It reads vault format notes to find dataName attributes.
- It does NOT call any LLM.
- A context with has_cycle=True must raise CycleDetectedError — the calling
  code (closure builder) sets BLOCKED_UNRESOLVED_REFERENCE.

## Tests
`tests/test_context_field_resolver.py`:
- Single context (parent=nil): fields collected from direct formats and implClasses.
- Two-level chain: inherited fields appear with inherited=True and correct context_level.
- Deduplication: field defined at both levels uses leaf definition.
- CCDate field inferred as LocalDate.
- context with has_cycle=True raises CycleDetectedError.
