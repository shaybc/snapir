# Prompt 20 — `StepImplementationInserterAgent`

## Context
Stage 5, Step 19. ServiceSkeletonGeneratorAgent (19) has produced a compiled skeleton.
This agent runs 6 passes — one per method body. Each pass is independent and
individually compilable.

## Reference
`Implementation_plan_V8.md` section 5 Phase 4 (sub-unit 5) — the 6-pass table.

## Files to create
```
agents/operation_assembly/step_implementation_inserter/
├── __init__.py
└── agent.py
```

## Pass definitions

| Pass | Method | Primary plan input | Supporting source |
|---|---|---|---|
| 1 | `deserializeRequest` | `SerializationPlan.request_parsing` | request JAXB DTO source |
| 2 | `initializeContext` | `ContextPlan.init_sequence` | context class source |
| 3 | `execute` | `RoutingPlan.steps` + `ContextPlan` | all cleaned implClass sources |
| 4 | `enrichWithDbLookups` | `SerializationPlan.db_lookups` | repository class sources |
| 5 | `serializeReply` | `SerializationPlan.response_building` | reply JAXB DTO source |
| 6 | `serializeErrorReply` | `SerializationPlan.error_response_building` | error reply JAXB DTO source |

## LLM instruction template (parameterised per pass)

```
You are implementing ONE method body in an existing Java service class.

OPERATION_ID: {operation_id}
METHOD_TO_IMPLEMENT: {method_name}
CURRENT_CLASS: {current_skeleton_with_previously_filled_methods}

PLAN:
{plan_section_json}

SUPPORTING_SOURCE:
{supporting_source_content}

RULES:
- Implement ONLY {method_name}. Do not modify any other method.
- Replace ONLY the 'throw new UnsupportedOperationException(...)' in {method_name}.
- Keep all other method stubs unchanged.
- Output the COMPLETE class with {method_name} implemented and all other stubs intact.
- No explanation. No markdown.

PASS-SPECIFIC RULES:

[PASS 1 - deserializeRequest]
Use JAXBContext to unmarshal xml string to {RequestDtoType}.
Apply decorator transformations from request_parsing.decorator_chain IN REVERSE ORDER.
Return the populated {RequestDtoType}.

[PASS 2 - initializeContext]
Follow init_sequence exactly in order.
For source=request_dto: ctx.set{FieldName}(req.get{FieldName}()).
For source=operation_fields: ctx.set{FieldName}("{value}").
For source=ini_value: ctx.set{FieldName}({value}).
Do not add any field assignments not in init_sequence.

[PASS 3 - execute]
Implement the opStep chain from routing_plan.steps.
For each step in order:
  - Call the step method (named after impl_class simple name): int rc = {stepMethod}(ctx);
  - Route based on transitions:
    on0Do=end: if (rc == 0) return null;  // serializeReply called by caller
    on4Do=MapError: if (rc == 4) { mapError(ctx); continue; }
    onOtherDo: else { fallback(ctx); }
- Implement on{N}Return body switches:
    if (rc == {N}) { return serializeErrorReply(buildErrorReply(ctx)); }
- The execute() method returns {ReplyDtoType} or throws.

[PASS 4 - enrichWithDbLookups]
For each db_lookup:
  String {fieldName} = {repositoryField}.findBy{KeyField}(ctx.get{KeyField}());
  ctx.set{FieldName}({fieldName});

[PASS 5 - serializeReply]
Build {ReplyDtoType} from context fields.
Apply decorator transformations from response_building.decorator_chain IN FORWARD ORDER.
Marshal to XML string using JAXBContext.
Return xml string.

[PASS 6 - serializeErrorReply]
Same pattern as pass 5 but for error_response_building plan.
```

## Execution loop
For passes 1-6 in order:
1. Send prompt with current class state.
2. Receive updated class.
3. Run `javac`.
4. If compile passes: store updated class, continue to next pass.
5. If compile fails: retry current pass with compiler error appended.
   After MAX_RETRIES: set blocking_reason=compile_failed on this pass. Stop.
6. After all 6 passes compile: run IBM dependency guard on complete class.

## IBM dependency guard (after pass 6)
```python
def run_ibm_guard(java_source: str, forbidden: list[str]) -> list[str]:
    """Returns list of forbidden patterns found. Empty = clean."""
```
If any forbidden pattern found: retry pass 3 with the found patterns highlighted.

## Tests
`tests/test_step_implementation_inserter.py` (mock LLM):
- Pass 1 only modifies deserializeRequest, other stubs unchanged.
- Pass 3 execute method contains routing for each step in plan.
- Compile failure on pass 2 triggers retry with error.
- IBM guard finding after pass 6 triggers retry.
- MAX_RETRIES exceeded on any pass → blocking_reason=compile_failed.
