# Prompt 26 — `trace_capture_tools/`

## Context
Stage 7, Step 24-25. Stub tools (25) exist.
These tools instrument both the legacy WSBCC system and the generated service
to capture execution traces for runtime equivalence comparison.

## Reference
`Implementation_plan_V8.md` section 5 Phase 6 (Runtime Equivalence Trace section),
`models/validation_models/` (ExecutionTrace, StepTrace, ContextAccess).

## Files to create
```
tools/trace_capture_tools/
├── __init__.py
├── trace_scenario_builder.py
├── legacy_trace_interceptor.py
└── generated_trace_interceptor.py
```

## `trace_scenario_builder.py`

```python
def derive_trace_scenarios(
    routing_plan: RoutingPlan
) -> list[TraceScenario]:
    """
    Derives test scenarios from the RoutingPlan.
    One scenario per distinct terminal path through the routing graph.

    A distinct terminal path = unique sequence of step_ids that ends at "end".
    Walk all possible paths from step_index=0 through all RC branches.
    Deduplicate by path signature (sorted step sequence).

    Every scenario must be named:
    - "success" for the RC=0-always path
    - "business_error_{step_id}" for on{N}Return paths
    - "technical_error_{step_id}" for non-zero non-return-body paths

    Returns list of TraceScenario(name, step_sequence, terminal_rc_values,
    request_xml_template).
    Minimum: one success scenario.
    """
```

## `legacy_trace_interceptor.py`

```python
def capture_legacy_trace(
    legacy_base_url: str,
    operation_id: str,
    channel: str,
    scenario: TraceScenario
) -> ExecutionTrace:
    """
    Sends scenario.request_xml_template to the legacy WSBCC system.
    The legacy system must be running with the TraceInterceptorServlet deployed
    (a separate Java servlet that wraps WSBCC and captures trace data).

    Polls the trace endpoint: GET {legacy_base_url}/trace/{operation_id}/latest
    Parses the trace JSON response into ExecutionTrace.
    Stores in execution_traces table with target="legacy".

    Raises LegacyTraceUnavailableError if legacy system is not running.
    """
```

The `TraceInterceptorServlet` is a Java component deployed alongside the legacy
WSBCC. Its specification:
- Intercepts every CCDSEServerOperation.execute() call.
- Records: steps_executed (with RC and timing), context writes per step,
  selected_reply_format, final_xml.
- Exposes: GET /trace/{operationName}/latest returning ExecutionTrace JSON.

Document the TraceInterceptorServlet interface in a comment block — the Java
implementation is a separate task.

## `generated_trace_interceptor.py`

```python
def enable_trace_interceptor(
    service_project_path: str,
    operation_id: str
) -> None:
    """
    Injects an ExecutionTraceInterceptor Spring AOP aspect into the generated
    service project.

    The aspect file (ExecutionTraceInterceptor.java) is pre-written and copied
    to the service project. It:
    - Intercepts every public method in the *Service class.
    - Records: method name, arguments, return value, timing.
    - For execute(): records step sequence, context mutations, reply format.
    - Writes trace JSON to a local file: /tmp/trace_{operationId}.json

    After enabling, rebuilds the service (mvn compile).
    """

def read_generated_trace(
    operation_id: str,
    scenario: TraceScenario,
    service_base_url: str
) -> ExecutionTrace:
    """
    Sends scenario.request_xml_template to the generated service.
    Reads /tmp/trace_{operationId}.json.
    Parses into ExecutionTrace.
    Stores in execution_traces table with target="generated".
    """
```

## Pre-written `ExecutionTraceInterceptor.java` template
Write this file to `tools/trace_capture_tools/ExecutionTraceInterceptor.java.template`.
It is a Spring AOP `@Around` aspect that captures trace data to file.

## Tests
`tests/test_trace_capture.py`:
- `derive_trace_scenarios` with a 2-step, 2-branch plan produces at least 2 scenarios.
- A plan with on{N}Return produces a "business_error" scenario.
- Scenarios deduplicated: identical path sequences produce one scenario.
