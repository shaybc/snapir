# Prompt 27 — `trace_comparator_tools/`

## Context
Stage 7. Trace capture tools (26) exist.
This deterministic tool compares legacy vs generated execution traces and
produces a structured comparison result.

## Reference
`Implementation_plan_V8.md` section 5 Phase 6 (TraceComparatorTool section,
failure classification table).

## Files to create
```
tools/trace_comparator_tools/
├── __init__.py
├── trace_comparator_tool.py
└── trace_report_writer.py
```

## `trace_comparator_tool.py`

```python
def compare_traces(
    legacy: ExecutionTrace,
    generated: ExecutionTrace
) -> TraceComparisonResult:
    """
    Compares two execution traces field by field.

    1. STEP SEQUENCE:
       Compare [step.step_id for step in legacy.steps_executed] vs generated.
       If sequences differ: step_sequence_match=False.
       step_sequence_diff = steps in legacy but not generated, and vice versa.

    2. RC PER STEP:
       For each step_id that appears in both traces at the same position:
       Compare step.return_code. If different: add RcMismatch.
       rc_per_step_match = True only if zero mismatches.

    3. CONTEXT WRITES:
       For each step in both traces at matching positions:
       For each context_write in legacy step: find matching write in generated step
       by field_name. Compare value_after. If missing or different: add
       ContextWriteMismatch.
       context_writes_match = True only if zero mismatches.

    4. REPLY FORMAT:
       Compare legacy.selected_reply_format vs generated.selected_reply_format.
       Compare legacy.reply_format_switched vs generated.reply_format_switched.
       reply_format_match = True if both match.

    5. FINAL XML:
       Call xml_diff_tool.compare_xml(legacy.final_xml, generated.final_xml).
       final_xml_match = True if passed.

    matched = True only if ALL FIVE comparisons pass.

    FAILURE CLASSIFICATION (from plan table):
    If !step_sequence_match OR !rc_per_step_match OR !reply_format_match:
        failure_class = routing_mismatch
    elif !context_writes_match AND matched_sequence:
        failure_class = conversion_gap
    elif !final_xml_match AND matched_sequence AND matched_rc:
        failure_class = equivalence_gap
    elif !final_xml_match AND !matched_sequence:
        failure_class = routing_mismatch
    else:
        failure_class = None

    Returns TraceComparisonResult.
    """
```

## `trace_report_writer.py`

```python
def write_comparison_to_db(
    conn,
    result: TraceComparisonResult,
    operation_id: str,
    channel: str,
    run_id: str,
    scenario: str
) -> None:
    """Writes to trace_comparisons table."""

def write_comparison_report(
    result: TraceComparisonResult,
    output_path: str
) -> None:
    """Writes a human-readable markdown report of the comparison."""

def generate_gate_summary(
    conn,
    run_id: str,
    operation_ids: list[str]
) -> str:
    """
    Reads all trace_comparisons for these operations.
    Returns a summary for Gate 4:
    - Operations fully matched: N
    - Operations with routing_mismatch: N (list)
    - Operations with conversion_gap: N (list)
    - Operations with equivalence_gap: N (list)
    """
```

## Tests
`tests/test_trace_comparator.py`:
- Identical traces: matched=True, failure_class=None.
- Different step sequence: failure_class=routing_mismatch.
- Same sequence, different RC at step 2: failure_class=routing_mismatch.
- Same sequence, same RC, missing context write: failure_class=conversion_gap.
- Same sequence, same RC, matching context, different final XML: failure_class=equivalence_gap.
- Different sequence AND different final XML: failure_class=routing_mismatch (not equivalence_gap).
