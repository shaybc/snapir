# Prompt 28 — `JavaValidationAgent`

## Context
Stage 7, Step 26. All validation tools (24-27) exist.
This agent orchestrates all 7 validation steps for each generated Java service.

## Reference
`Implementation_plan_V8.md` section 5 Phase 6 (7 validation steps).

## Files to create
```
agents/java_validation/
├── __init__.py
└── agent.py
```

## Agent definition

```python
from google.adk.agents import SequentialAgent

java_validation_agent = SequentialAgent(
    name="JavaValidationAgent",
    description="Runs all 7 validation steps for a generated Java service.",
    sub_agents=[...],
)
```

## 7 validation steps

### Step 1 — Compile/build
```python
def validate_compile(generated_path: str) -> JavaBuildResult:
    """Run 'mvn compile' on the generated project."""
```
If fails: set generated_artifacts.status=blocked,
blocking_reason=compile_failed. Stop validation.

### Step 2 — IBM dependency guard (blocking)
```python
def validate_ibm_guard(generated_path: str, forbidden: list[str]) -> list[str]:
    """Scan for IBM patterns."""
```
If any found: set blocking_reason=ibm_dependency_found. Stop.

### Step 3 — Code equivalence review (LLM)
Inline LlmAgent call comparing generated service against native Java:
```
Does the generated Java service faithfully implement the logic in the
native Java service class? Check: method names, routing logic, context
mutations, DB calls, error handling.
Output JSON: {"passed": true|false, "issues": [...]}
```
If failed: set blocking_reason=equivalence_gap.

### Step 4 — Golden XML tests
For each GoldenXmlPair:
```python
def run_golden_xml_test(pair: GoldenXmlPair, service_base_url: str) -> XmlDiffResult:
    """Send pair.request_xml to running service. Compare response to expected."""
```
Start the service with stub_server for backend dependencies.
If any diff: record failure_class=conversion_gap.

### Step 5 — Runtime equivalence trace (critical)
```python
def run_trace_comparison(
    operation_id: str,
    channel: str,
    routing_plan: RoutingPlan,
    legacy_base_url: str,
    service_base_url: str,
    run_id: str
) -> list[TraceComparisonResult]:
    """
    1. Build scenarios from RoutingPlan.
    2. Capture legacy trace for each scenario.
    3. Capture generated trace for each scenario.
    4. Compare via TraceComparatorTool.
    5. Store all comparisons in trace_comparisons table.
    """
```
Any routing_mismatch → set failure_class=routing_mismatch.
Any conversion_gap → set failure_class=conversion_gap.

### Step 6 — Behavioral equivalence
Send same request to legacy WSBCC and to generated service.
Compare final XML responses using xml_diff_tool.
This is a coarser check than the trace — confirms end-to-end output equivalence.

### Step 7 — Performance benchmark (reporting only, non-blocking)
```python
def run_performance_benchmark(service_base_url: str, request_xml: str) -> dict:
    """Send 100 requests. Report p50/p95 response time."""
```
Writes to ValidationReport. Does not block on poor performance in V1.

## Validation feedback routing
```python
def route_validation_failure(result: ValidationReport) -> str:
    """
    Returns the feedback target agent name based on failure_class:
    build_failure      -> JavaServiceGenerationAgent
    conversion_gap     -> IbmJavaCleanerAgent (re-convert affected implClass)
    equivalence_gap    -> JavaServiceGenerationAgent
    shared_component_gap -> IbmJavaCleanerAgent (shared component)
    routing_mismatch   -> StepImplementationInserterAgent (re-run pass 3)
    validation_fixture_gap -> validation_tools (regenerate fixture)
    """
```

## Tests
`tests/test_java_validation_agent.py`:
- IBM pattern found in step 2 → stops at step 2, no further steps run.
- routing_mismatch from trace → failure_class=routing_mismatch in ValidationReport.
- All 7 steps pass → generated_artifacts.status=validated.
