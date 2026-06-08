# Prompt 16 — `ContextToJavaConverterAgent`

## Context
Stage 4, Step 14. ContextFieldResolverTool (Prompt 11) has pre-built inventories.
This agent converts a ContextFieldInventory into a typed flat Java class.

## Reference
`Implementation_plan_V8.md` section 5 Phase 3 (XML context definitions section).

## Files to create
```
agents/source_conversion/context_to_java_converter/
├── __init__.py
└── agent.py
```

## LLM instruction (CONTEXT_TO_JAVA_INSTRUCTION)

```
You are generating a typed Java context class from a field inventory.

A WSBCC context is a runtime data carrier. The generated class must be a flat
plain Java class — no inheritance, no framework annotations.

CONTEXT_ID: {context_id}
CONTEXT_CHAIN: {context_chain}  (ordered leaf-first, root last)
FIELDS: {fields_json}
  Each field has: name, java_type, context_level, inherited, source

RULES:
1. One flat class. No extends. No @annotations.
2. One private field per entry in FIELDS.
   Use the java_type from the field inventory.
3. Getter and setter for every field.
   Getter: get{FieldName}(), Setter: set{FieldName}({type} value).
4. No-argument constructor.
5. Add a comment on each inherited field:
   // inherited from {context_level}
6. Package: {java_package_base}.context
7. Class name: {context_id} (use the context_id as the class name).
8. No business logic. No DB calls. No XML handling.
9. Output the Java source only. No explanation.

FIELDS:
{fields_json}
```

## Tools

```python
def get_context_inventory(
    conn, context_id: str, channel: str, run_id: str
) -> ContextFieldInventory:
    """Reads from context_field_inventories table."""

def submit_context_class(
    conn, task_id: str, java_source: str, output_path: str, run_id: str
) -> str:
    """Writes context class, runs javac. Returns 'compiled' | 'compile_failed'."""
```

## Rules
- Generated context class is always flat — no Java inheritance hierarchy.
- The WSBCC context inheritance is captured by the `inherited` flag in the
  field list, not by Java extends.
- Inherited fields get a comment but are otherwise identical to local fields.
- This agent does not reason about what the fields mean — it mechanically
  converts the inventory to a Java class.

## Tests
`tests/test_context_to_java_converter.py`:
- Single-level context: class with all local fields, no inherited comments.
- Two-level chain: inherited fields have // inherited from X comment.
- Field name used as Java identifier (camelCase if needed).
- java_type=LocalDate generates import java.time.LocalDate.
