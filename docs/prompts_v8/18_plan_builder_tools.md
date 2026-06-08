# Prompt 18 — `RoutingPlanBuilderTool` + `ContextPlanBuilderTool` + `SerializationPlanBuilderTool`

## Context
Stage 5, Step 17. All Phase 3 agents (14-17) exist.
These three deterministic tools must be built and tested independently before
any LLM assembly agent is connected. They are the foundation of Phase 4.

## Reference
`Implementation_plan_V8.md` section 5 Phase 4 (sub-units 1, 2, 3).

## Files to create
```
tools/conversion_tools/routing_plan_builder_tool.py
tools/conversion_tools/context_plan_builder_tool.py
tools/conversion_tools/serialization_plan_builder_tool.py
```

## `routing_plan_builder_tool.py`

```python
def build_routing_plan(
    conn,
    operation_id: str,
    channel: str,
    run_id: str
) -> RoutingPlan:
    """
    Reads the OperationClosure (must be READY) for this operation.
    Builds a RoutingPlan with fully resolved transitions.

    For each step in closure.included_opstep_ids (in order):
      1. Assign step_index (0-based).
      2. Read transitions from closure.routing_graph[step_id].
         Transitions map RC strings to next step_id or terminal signals.
      3. Resolve step names to step_indices where possible.
         Terminal signals "end" and "next" remain as string constants.
      4. Read return_body_switches from closure's aggregated map.
      5. Read parameters from opStep metadata.
      6. Build RoutingStep.

    Detect unreachable steps: any step in included_opstep_ids that cannot be
    reached from step_index=0 following any transition path.
    Log warnings for unreachable steps (do not block READY closure for this).

    Store RoutingPlan in routing_plans table.
    Return RoutingPlan.
    """
```

RC resolution rules:
- Numeric string keys ("0", "4", "8"): map to exact RC values.
- "other" key: maps to onOtherDo target.
- "timeout" key: maps to onTimeoutDo target.
- All step name targets must resolve to a step_index in included_opstep_ids.
- If a target step name is not in included_opstep_ids: log warning, keep as string.

## `context_plan_builder_tool.py`

```python
def build_context_plan(
    conn,
    operation_id: str,
    channel: str,
    run_id: str
) -> ContextPlan:
    """
    Reads OperationClosure for this operation.
    Reads ContextFieldInventory from context_field_inventories.
    Reads operation_fields and ini_values from closure.

    Builds init_sequence:
    1. Fields initialized from request DTO (source=request_dto):
       Fields that appear in csRequestFormat's ParseStep list.
    2. Fields initialized from operation_fields (source=operation_fields):
       Parse comma-separated "key=value" pairs from closure.operation_fields.
    3. Fields initialized from ini_values (source=ini_value):
       Each iniValue entry.
    4. Fields written by opSteps (source=opstep_write):
       These are NOT pre-initialized — marked for reference only.

    Order: request_dto fields first, then operation_fields, then ini_values.

    Store ContextPlan in context_plans table.
    Return ContextPlan.
    """
```

## `serialization_plan_builder_tool.py`

```python
def build_serialization_plan(
    conn,
    operation_id: str,
    channel: str,
    run_id: str,
    vault_root: str
) -> SerializationPlan:
    """
    Reads OperationClosure for this operation.
    Reads ServiceLayerRequirements for csRequestFormat and csReplyFormat.
    Reads decorator chains from closure.formats.decorator_chains.

    Build request_parsing (list[ParseStep]):
    For each field in csRequestFormat:
      - xml_path: derived from tag structure (CCXML nesting + dataName)
      - context_field: the dataName
      - decorator_chain: REVERSED list from closure.formats.decorator_chains
        for this field (unformat direction = reverse order)
      - java_type: from ContextFieldInventory

    Build response_building (list[BuildStep]):
    For each field in csReplyFormat:
      - context_field: the dataName
      - xml_element: element name from tag structure
      - decorator_chain: FORWARD list from closure.formats.decorator_chains
        (format direction = forward order)
      - nullable: True if nilDecorator appears in decorator chain

    Build error_response_building: same logic for csErrorReplyFormat.

    Build db_lookups: read from closure.formats.db_lookups.
    CCTableFormat nodes must be in db_lookups, never in request_parsing
    or response_building.

    Store SerializationPlan in serialization_plans table.
    Return SerializationPlan.
    """
```

## Critical rules
- Decorator chain direction: ParseStep uses REVERSED chain (unformat direction).
  BuildStep uses FORWARD chain (format direction).
- CCTableFormat appears ONLY in db_lookups. Never in parse or build steps.
- These three tools run before any LLM. If any raises, Phase 4 does not start
  for that operation.
- All three tools read from the READY closure — they never re-query source
  artifacts or vault files directly.

## Tests
`tests/test_plan_builders.py`:
- RoutingPlan: step transitions resolved to step_index for named targets.
- RoutingPlan: unreachable step logged as warning, not error.
- ContextPlan: init_sequence has request_dto fields before operation_fields.
- SerializationPlan: decorator_chain in ParseStep is REVERSED vs FormatSet.
- SerializationPlan: CCTableFormat in db_lookups, absent from request_parsing.
- SerializationPlan: nullable=True for fields with nilDecorator in chain.
