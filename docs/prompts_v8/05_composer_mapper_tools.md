# Prompt 05 — `composer_mapper_tools/`

## Context
Stage 2, Step 5. All foundation + intake tools exist.
This package reads the markdown vault produced by composer-mapper and populates
the SQLite DB. It is the bridge between the static vault and the live pipeline.
The pipeline never reads dse.ini directly — only this package reads the vault.

## Reference
`Implementation_plan_V8.md` sections 5 Phase 1 (What gets populated table),
11 (composer_mapper_tools), and `ARCHITECTURE.md` sections 8-14.

## Package structure

```
tools/composer_mapper_tools/
├── __init__.py
├── vault_reader.py          ← discovers and reads vault markdown files
├── frontmatter_parser.py    ← parses YAML frontmatter from any vault note
├── operation_parser.py      ← parses operations/*.md notes
├── opstep_parser.py         ← parses opsteps/*.md notes
├── format_parser.py         ← parses formats/*.md including Structure section
├── context_parser.py        ← parses contexts/*.md notes
├── java_class_parser.py     ← parses classes/**/*.md notes
├── channel_registry_parser.py ← parses analysis/channel-operation-registry.md
├── channel_note_parser.py   ← parses channels/{CHANNEL}.md notes
└── vault_importer.py        ← orchestrates full vault import into DB
```

## `frontmatter_parser.py`
```python
def parse_frontmatter(md_text: str) -> dict:
    """Extracts YAML between --- delimiters. Returns empty dict if absent."""

def parse_section(md_text: str, section_heading: str) -> str:
    """Returns text content of a ## Section heading. Empty string if absent."""
```

## `operation_parser.py`
Reads every field from the vault note as specified in the plan Phase 1 table:
```python
def parse_operation_note(md_text: str, source_path: str) -> ComposerOperation:
    """
    Reads frontmatter: entity_id, source_file, source_hash, channel,
    entry_step, host_key, operation_fields, ini_values, conversion_status.
    Reads body: ## Steps (list), ## Request Format, ## Reply Format,
    ## Other Formats -> ref_formats dict.
    """
```

## `opstep_parser.py`
```python
def parse_opstep_note(md_text: str, source_path: str) -> ComposerOpStep:
    """
    Reads frontmatter: entity_id, source_file, source_hash, onlyFor,
    used_by_operations, conversion_status.
    Reads body:
    - ## Parameters -> dict of k: v lines
    - ## Transitions -> dict of on*Do: target lines
    - ## Return Body Switches -> dict of RC: format_name lines
    """
```

## `format_parser.py`
```python
def parse_format_note(md_text: str, source_path: str) -> ComposerFormat:
    """
    Reads frontmatter: entity_id, source_file, source_hash, shared,
    used_by_operations, conversion_status.
    Reads body:
    - ## Structure -> parse tag tree including decorator lines
      (lines starting with 'decorator: ' are decorator entries)
      -> builds decorator_chains dict: formatter_node_id -> [decorator_tag_names]
      -> builds transparent_ccxml_nodes list
    - ## Database Lookups -> list of {field_name, from_table, from_column, key_value_field}
    - ## Serialization Notes -> list of flag strings
    """
```

## `java_class_parser.py`
```python
def parse_java_class_note(md_text: str, source_path: str) -> ComposerJavaClass:
    """
    Reads frontmatter: entity_id (FQCN), source_file, source_hash, shared,
    used_by_steps, parent_class, interfaces, conversion_status.
    Reads body:
    - ## Behavior Type -> list
    - ## Return Codes -> dict[rc_value: list[meanings]]
    - ## Setter Methods -> list
    - ## IBM Dependency Warning -> has_ibm_dependency=True, ibm_imports list
    """
```

## `channel_registry_parser.py`
```python
def parse_channel_operation_registry(
    registry_md_path: str
) -> list[tuple[str, str, str]]:
    """
    Reads analysis/channel-operation-registry.md.
    Returns list of (operation_name, channel, xml_file_path) tuples
    from the markdown table rows.
    """
```

## `channel_note_parser.py`
```python
def parse_channel_note(md_text: str, channel: str) -> list[tuple[str, str, str]]:
    """
    Reads channels/{CHANNEL}.md.
    Parses tag->FQCN mappings from the tag mappings section.
    Returns list of (tag_name, fqcn, channel) tuples.
    """
```

## `vault_importer.py`
Orchestrates the full import in this order:
1. Read `analysis/channel-operation-registry.md` → populate `channel_operations`
2. Read `channels/*.md` → populate `tag_registry`
3. Read `operations/*.md` → populate `source_artifacts` (kind=operation)
4. Read `opsteps/*.md` → populate `source_artifacts` (kind=opStep)
5. Read `formats/*.md` → populate `source_artifacts` (kind=format)
6. Read `contexts/*.md` → populate `source_artifacts` (kind=context)
7. Read `classes/**/*.md` → populate `source_artifacts` (kind=java_class)
8. Populate `operations` table from `channel_operations` filtered by
   `run_config.target_channels`
9. Apply `include_operations` filter (keep only listed if set)
10. Apply `exclude_operations` filter (remove listed if set)
11. Log counts: operations, opSteps, formats, contexts, java_classes,
    unresolved references

```python
def import_vault(
    conn,
    vault_root: str,
    run_config: RunConfig
) -> VaultImportSummary:
    """Returns counts per entity type and list of unresolved references."""
```

## Rules
- Parse errors on individual vault files must be logged and skipped, never crash
  the whole import. Collect all errors and include in VaultImportSummary.
- The `operations` table is populated AFTER `channel_operations` so the filter
  logic has complete data.
- `include_operations` is applied before `exclude_operations`. If both are set
  and overlap, exclude wins for the overlap.
- Use `source_path` (the vault `.md` file path) as the source for the vault note,
  not `source_file` from frontmatter. Both are stored separately.

## Tests
`tests/test_composer_mapper_tools.py`:
- `parse_frontmatter` handles missing --- delimiters gracefully.
- `parse_opstep_note` correctly extracts Return Body Switches section.
- `parse_format_note` correctly builds decorator_chains from Structure section.
- `parse_java_class_note` sets has_ibm_dependency=True when IBM Dependency
  Warning section is present.
- `import_vault` with INCLUDE_OPERATIONS=["OpA"] excludes OpB from operations table.
- `import_vault` with EXCLUDE_OPERATIONS=["OpA"] keeps OpB, removes OpA.
