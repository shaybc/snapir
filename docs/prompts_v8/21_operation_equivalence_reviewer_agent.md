# Prompt 21 — `OperationEquivalenceReviewAgent`

## Context
Stage 5, Step 20. StepImplementationInserterAgent (20) has produced a complete,
compiled service class. This agent reviews it against all four inputs.

## Reference
`Implementation_plan_V8.md` section 5 Phase 4 (sub-unit 6).

## Files to create
```
agents/operation_assembly/operation_equivalence_reviewer/
├── __init__.py
└── agent.py
```

## LLM instruction

```
You are reviewing a generated Java service class for correctness.

You have four inputs to check against. Verify each checklist item.

OPERATION_ID: {operation_id}
CHANNEL: {channel}
ORIGINAL_WSBCC_XML: {operation_xml}
ROUTING_PLAN: {routing_plan_json}
CONTEXT_PLAN: {context_plan_json}
SERIALIZATION_PLAN: {serialization_plan_json}
GENERATED_SERVICE_CLASS: {java_source}

CHECKLIST (verify every item):
1. Every step_id in routing_plan.steps appears in the execute() method.
2. Every RC transition in routing_plan (all entries in each step's transitions)
   has a corresponding if/else/switch branch in execute().
3. Every on{N}Return in routing_plan appears as an error reply switch in execute().
4. Every field in context_plan.init_sequence appears in initializeContext().
5. Every ParseStep in serialization_plan.request_parsing appears in deserializeRequest().
6. Every DbLookupRequirement in serialization_plan.db_lookups appears in enrichWithDbLookups().
7. No IBM imports remain.
8. No logic appears in DTO classes.
9. The execute() method creates a new context instance per call (not a shared field).
10. Return types match the plan.

For each issue found, classify using:
- behavior_mismatch: missing step, missing RC branch, missing return_body_switch
- missing_error_format: missing on{N}Return implementation
- compile_issue: structural Java problem

Output JSON:
{
  "missing_steps": ["step_ids missing from execute"],
  "missing_rc_branches": ["step_id:RC description"],
  "context_mutation_issues": ["description"],
  "logic_differences": ["description"],
  "confidence": "high|medium|low",
  "review_status": "approved|needs_revision|needs_human_review"
}
Output ONLY JSON. No explanation.
```

## Post-review actions
- `approved` + confidence=high: mark operation as assembly_complete.
- `approved` + confidence=medium: log warning, mark assembly_complete.
- `needs_revision`: feed issues back to StepImplementationInserterAgent (pass 3).
  Maximum 2 revision cycles before escalating to needs_human_review.
- `needs_human_review`: set HumanReviewItem with full evidence.

## Human Gate 3
After pilot batch assembly complete:
```
=== Human Gate 3 ===
Operations assembled: {N}
Approved: {N}
Needs revision (pending retry): {N}
Needs human review: {N}

Sample assembled services: [paths]
Review and approve pilot batch? (yes/no)
```

## Tests
`tests/test_operation_equivalence_reviewer.py` (mock LLM):
- Missing RC branch in execute → missing_rc_branches list populated.
- needs_revision → revision fed back to inserter.
- 2 revision cycles with persistent issues → needs_human_review.
