# Prompt 14 — `IbmJavaCleanerAgent`

## Context
Stage 4, Step 12. All Stage 1-3 components exist.
This is the first LLM agent that generates code. It converts IBM Java implClass
source files to clean, IBM-free native Java.

## Reference
`Implementation_plan_V8.md` section 5 Phase 3 (IBM Java implClasses section),
`wsbcc_developer_manual_v2.md` section 8 (opSteps, implClass contract),
`skills/conversion_rules_skill.md` Rule 8 (preserve business logic exactly).

## Files to create
```
agents/source_conversion/ibm_java_cleaner/
├── __init__.py
└── agent.py
```

## Agent definition

```python
from google.adk.agents import LlmAgent

ibm_java_cleaner_agent = LlmAgent(
    name="IbmJavaCleanerAgent",
    description="Converts IBM Java implClass source to clean native Java.",
    model=AGENT_MODEL,
    instruction=IBM_CLEANER_INSTRUCTION,
    tools=[get_conversion_task, submit_cleaned_class, request_human_review],
)
```

## LLM instruction (IBM_CLEANER_INSTRUCTION)

```
You are converting an IBM WebSphere WSBCC Java implClass to clean native Java.

You will receive:
- JAVA_SOURCE: the full Java source code to convert
- PARENT_CLASS: the FQCN of the class this extends (may be null)
- INTERFACES: list of interfaces this class implements
- IBM_IMPORTS: list of IBM-specific imports to remove
- BEHAVIOR_TYPE: one or more of: db_accessor, error_mapper, validator,
  formatter, collector, unknown

Your job is to produce clean Java that preserves EXACTLY the business logic
while removing all IBM/WAS framework dependencies.

RULES — follow all of them:
1. Remove ALL imports starting with com.ibm.*, com.ibm.dse.*, javax.ejb.*,
   javax.rmi.*, org.omg.*
2. Replace IBM context access:
   context.setValueAt("FieldName", value) -> ctx.setFieldName(value)
   context.getValueAt("FieldName")        -> ctx.getFieldName()
   Where ctx is the typed context class parameter.
3. Replace IBM connection/JDBC patterns:
   context.getConnection() -> dataSource.getConnection()
   Inject DataSource as a constructor parameter.
4. Preserve the execute() method signature: public int execute() throws Exception
5. Preserve ALL return code values EXACTLY. A return of 4 must stay 4.
6. Preserve ALL business logic inside method bodies EXACTLY.
   Do not simplify, combine, or refactor business logic.
7. Remove extends CCOperationStep / implements OperationStepInterface.
   The clean class has no IBM superclass.
8. Keep all setter methods (set{AttributeName}) — these are called by the
   assembler with XML attribute values.
9. If PARENT_CLASS contains 'FormatDecoratorHolder':
   Keep addDecoration(String s) and removeDecoration(String s) methods.
   Remove initializeFrom(Tag tag) — replace with a plain constructor or setters.
10. If PARENT_CLASS contains 'AttributeXmlFormatDecoratorImpl':
    Keep formatXmlAttributes() logic but rewrite without IBM Tag parameter.
11. If you cannot determine what an IBM call does: add a TODO comment and
    flag for human review. Do NOT guess.
12. Output ONLY the clean Java source. No explanation, no markdown.

PARENT_CLASS: {parent_class}
INTERFACES: {interfaces}
IBM_IMPORTS: {ibm_imports}
BEHAVIOR_TYPE: {behavior_types}

JAVA_SOURCE:
{java_source}
```

## Tool: `get_conversion_task`
```python
def get_conversion_task(conn, task_id: str) -> ConversionTaskPacket:
    """Reads a pending ibm_java conversion task from agent_tasks."""
```

## Tool: `submit_cleaned_class`
```python
def submit_cleaned_class(
    conn,
    task_id: str,
    cleaned_java_source: str,
    output_path: str,
    run_id: str
) -> str:
    """
    Writes the cleaned Java source to output_path.
    Runs javac on the file.
    If compile succeeds: writes to native_java_artifacts, status=converted.
    If compile fails: increments attempt_number, status=failed.
    Returns 'compiled' | 'compile_failed'.
    """
```

## Tool: `request_human_review`
```python
def request_human_review(
    conn,
    task_id: str,
    reason: str,
    evidence: list[str]
) -> None:
    """Sets task status=needs_human_review, blocking_reason=needs_human_mapping."""
```

## Retry logic
- On compile failure: retry up to MAX_AGENT_TASK_RETRIES times.
  Include compiler error in the next LLM prompt.
- On 3rd failure: set blocking_reason=compile_failed, status=blocked.
- If LLM output contains TODO comments: set status=needs_human_review,
  blocking_reason=needs_human_mapping.

## Context contract determination (from parent_class)

| parent_class contains | Contract | Key methods to preserve |
|---|---|---|
| `CCOperationStep` or `OperationStepInterface` | opStep executor | execute(), all setters |
| `FormatDecoratorHolder` | value decorator | addDecoration(String), removeDecoration(String) |
| `AttributeXmlFormatDecoratorImpl` | attribute decorator | formatXmlAttributes() |
| None / unknown | generic | execute() if present, all public methods |

## Tests
`tests/test_ibm_java_cleaner_agent.py` (use mock LLM):
- IBM import removal verified in output.
- context.setValueAt replaced with typed setter.
- Return codes preserved.
- Compile failure → retry → blocked after MAX_RETRIES.
- TODO comment in output → needs_human_review.
