# Prompt 29 — `DocumentationReportAgent`

## Context
Stage 8, Step 25. All validation agents exist.
This agent produces incremental per-operation documentation and the final
migration report.

## Reference
`Implementation_plan_V8.md` section 5 Phase 8.

## Files to create
```
agents/documentation_report/
├── __init__.py
└── agent.py
```

## LLM instruction (per-operation doc)

```
You are generating migration documentation for one converted operation.

OPERATION_ID: {operation_id}
CHANNEL: {channel}
ORIGINAL_WSBCC_XML: {operation_xml}
GENERATED_SERVICE_PATH: {service_path}
ROUTING_PLAN_SUMMARY: {routing_plan_summary}
VALIDATION_REPORT: {validation_report_json}
SHARED_COMPONENTS: {shared_components_list}

Generate a migration note in Markdown:
1. ## Operation: {operation_id}
2. ### Summary: one paragraph describing what this operation does.
3. ### Conversion notes: what was converted, what was shared, any human review items.
4. ### Validation results: pass/fail per step, any routing_mismatch details.
5. ### Files generated: list of generated file paths.
6. ### Known issues: list from validation report (empty if none).

Output Markdown only. No JSON.
```

## Final report
After all batches complete, aggregate into a final report:

```python
def generate_final_report(conn, run_id: str, output_path: str) -> None:
    """
    Reads all ValidationReports, operation docs, and run statistics.
    Writes a comprehensive Markdown report to output_path:
    - Executive summary
    - Operations migrated (per channel)
    - Blocked operations with reasons
    - Shared components promoted to common-lib
    - Validation pass rates
    - Routing mismatches found and resolved
    - Human review items
    - Performance benchmarks
    - Files generated
    """
```

## Human Gate 4
```
=== Human Gate 4 ===
Migration complete.

Operations validated: {N}/{total}
Blocked (needs human review): {N}
Shared components in common-lib: {N}
Routing mismatches detected and fixed: {N}

Final report: {output_path}

Approve for production? (yes/no)
```

## Tests
`tests/test_documentation_report_agent.py` (mock LLM):
- Per-operation doc contains operation_id in heading.
- Final report includes all operations.
- Gate 4 output includes routing_mismatch count.
