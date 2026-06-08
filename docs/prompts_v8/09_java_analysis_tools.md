# Prompt 09 — `java_analysis_tools/`

## Context
Stage 3, Step 10. All Stage 1-2 components exist.
These tools read actual Java source files from disk (not the vault).
They are used by IbmJavaCleanerAgent and closure builder tools to inspect
live source files.

## Reference
`Implementation_plan_V8.md` sections 5 Phase 3 (IBM Java cleaner inputs),
`ARCHITECTURE.md` section 4 (Java source parsing).

## Package structure
```
tools/java_analysis_tools/
├── __init__.py
├── java_source_reader.py    ← reads raw Java source from disk
├── java_slicer.py           ← extracts specific methods from a Java class
└── java_structural_summariser.py  ← produces a structured summary of a Java class
```

## `java_source_reader.py`
```python
def read_java_source(source_file_path: str) -> str:
    """
    Reads Java source file from disk.
    Raises FileNotFoundError with descriptive message if not found.
    Returns raw UTF-8 source string.
    Max size guard: raise if > MAX_SOURCE_CHARS_PER_CONVERSION.
    """

def resolve_source_path(
    composer_root: str,
    fqcn: str
) -> str | None:
    """
    Attempts to resolve a FQCN to a .java file path under composer_root.
    e.g. com.bank.ops.GetClientLinksSP ->
         composer_root/com/bank/ops/GetClientLinksSP.java
    Returns None if not found.
    """
```

## `java_slicer.py`
```python
def extract_method(source: str, method_name: str) -> str | None:
    """
    Extracts the full text of a named method including its signature and body.
    Returns None if the method is not found.
    Uses balanced-brace counting, not an AST parser.
    """

def extract_execute_method(source: str) -> str | None:
    """Convenience wrapper for extract_method(source, 'execute')."""

def extract_imports(source: str) -> list[str]:
    """Returns all import statements as a list of FQCN strings."""

def extract_ibm_imports(source: str) -> list[str]:
    """Returns only IBM/WAS import statements."""
```

## `java_structural_summariser.py`
```python
def summarise_java_class(
    source: str,
    parent_class: str | None,
    interfaces: list[str]
) -> JavaClassSummary:
    """
    Produces a structured summary for use in LLM conversion prompts.
    Includes: class name, package, parent_class, interfaces,
    method names, setter names, ibm_imports, return_codes,
    behavior_types, context_access_patterns.
    """

def detect_context_access_patterns(source: str) -> list[str]:
    """
    Scans for setValueAt / getValueAt / setValue / getValue calls.
    Returns list of field name strings extracted from the calls.
    e.g. 'context.setValueAt("ClientId", value)' -> "ClientId"
    """
```

`JavaClassSummary` is a plain dataclass (not a DB model):
- class_name, package, fqcn, parent_class, interfaces, methods, setters,
  ibm_imports, return_codes, behavior_types, context_fields_written,
  context_fields_read, source_char_count

## Rules
- These tools read directly from disk, not from the vault.
- They are called by IbmJavaCleanerAgent to get the actual source before
  sending to the LLM.
- The vault `## Setter Methods` and `## Return Codes` sections are metadata
  for the closure — these tools extract the same information directly from
  source for conversion use.

## Tests
`tests/test_java_analysis_tools.py`:
- `extract_method` finds a named method in a sample Java source.
- `extract_ibm_imports` returns only com.ibm.* lines.
- `detect_context_access_patterns` extracts field names from setValueAt calls.
- `resolve_source_path` maps FQCN to correct path structure.
