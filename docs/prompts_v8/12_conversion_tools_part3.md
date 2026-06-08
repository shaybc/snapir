# Prompt 12 — `conversion_tools/` Part 3: operation_xml_loader + format_dependency_resolver + java_impl_resolver

## Context
Stage 3. Prompts 10 and 11 tools exist.
These three tools are called by `OperationClosureBuilderTool` (Prompt 13).
Each resolves one major dependency category for the closure.

## Reference
`Implementation_plan_V8.md` section 11 (tool definitions), section 5 Phase 2
(OperationClosureBuilderTool sub-tools), `wsbcc_developer_manual_v2.md`
sections 3, 6 (dse.ini, formats).

## Files to create
```
tools/conversion_tools/operation_xml_loader_tool.py
tools/conversion_tools/format_dependency_resolver_tool.py
tools/conversion_tools/java_impl_resolver_tool.py
```

## `operation_xml_loader_tool.py`

```python
def load_operation_xml(
    conn,
    operation_name: str,
    channel: str,
    run_id: str,
    composer_root: str
) -> str:
    """
    1. Looks up xml_file_path in channel_operations table
       WHERE operation_name=operation_name AND channel=channel AND run_id=run_id.
    2. Constructs absolute path: composer_root / xml_file_path.
    3. Reads and returns raw XML content (UTF-8).
    Raises OperationXmlNotFoundError with detail if not found.
    """

def get_operation_xml_path(
    conn,
    operation_name: str,
    channel: str,
    run_id: str
) -> str:
    """Returns the xml_file_path without reading the file."""
```

## `format_dependency_resolver_tool.py`

```python
def resolve_format_dependencies(
    conn,
    format_ids: list[str],
    run_id: str,
    vault_root: str
) -> FormatSet:
    """
    Recursively resolves all format dependencies starting from format_ids.

    For each format_id:
      1. Look up in source_artifacts. If not found: add to unresolved_format_refs,
         set ClosureBlockingIssue(BLOCKED_MISSING_FORMAT).
      2. Read vault note for this format.
      3. Parse Structure section via decorator_chain_resolver_tool.
         Collect formatter_tags and decorator_chains.
      4. Parse Database Lookups section. Collect db_lookups.
      5. Parse Serialization Notes. Collect transparent_ccxml_nodes.
      6. Check for nested refFmt references in the vault note body.
         Add any nested format_ids to the resolution queue (recursive).
      7. For each formatter_tag: look up in tag_registry.
         If not found: add ClosureBlockingIssue(BLOCKED_UNKNOWN_TAG).
      8. For each decorator tag: look up in tag_registry.
         If not found: add ClosureBlockingIssue(BLOCKED_UNKNOWN_TAG).

    Returns FormatSet with all collected data and any blocking issues.
    """
```

### Recursive resolution
Use a visited set to prevent infinite loops on shared formats.
The same format may appear in multiple ref_format roles — visit it only once.

## `java_impl_resolver_tool.py`

```python
def resolve_java_impls(
    conn,
    opstep_ids: list[str],
    run_id: str,
    composer_root: str
) -> tuple[list[JavaClassRef], list[ClosureBlockingIssue]]:
    """
    For each opStep_id in opstep_ids:

    1. Read impl_class from source_artifacts (kind=opStep).
       If impl_class is None or blank:
         - Read opStep tag name from metadata.
         - Look up in tag_registry WHERE tag_name=opStep_tag AND run_id=run_id.
         - If found: use fqcn from tag_registry.
         - If not found: add ClosureBlockingIssue(BLOCKED_MISSING_IMPL_CLASS).
           Skip this opStep.

    2. Look up FQCN in source_artifacts (kind=java_class).
       If not found in vault: add ClosureBlockingIssue(BLOCKED_MISSING_IMPL_CLASS).
       Skip this class.

    3. Verify source file exists on disk:
       Call resolve_source_path(composer_root, fqcn).
       If None: add ClosureBlockingIssue(BLOCKED_MISSING_IMPL_CLASS).
       Skip.

    4. Build JavaClassRef from source_artifacts metadata:
       fqcn, source_file, parent_class, interfaces,
       has_ibm_dependency, ibm_imports, return_codes, shared.

    Returns (list[JavaClassRef], list[ClosureBlockingIssue]).
    """
```

## Rules
- `format_dependency_resolver_tool` resolves recursively but uses a visited set.
- `java_impl_resolver_tool` checks both the vault (for metadata) and disk
  (for file existence). A class can be in the vault but missing from disk.
- All three tools are deterministic — no LLM.
- Blocking issues are returned, not raised — the caller (closure builder)
  aggregates them.

## Tests
`tests/test_dependency_resolvers.py`:
- load_operation_xml returns correct XML when channel_operations row exists.
- load_operation_xml raises OperationXmlNotFoundError when not found.
- resolve_format_dependencies recursively finds nested formats.
- resolve_format_dependencies flags unknown decorator tag as BLOCKED_UNKNOWN_TAG.
- resolve_java_impls falls back to tag_registry when impl_class is absent.
- resolve_java_impls flags missing source file as BLOCKED_MISSING_IMPL_CLASS.
