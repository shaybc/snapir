# Prompt 25 — `stub_tools/` + `log_replay_tools/`

## Context
Stage 7, Step 23. Validation tools (24) exist.
Stubs and log replay cases are the test fixtures used by JavaValidationAgent
for golden XML tests and behavioral equivalence testing.

## Reference
`Implementation_plan_V8.md` section 5 Phase 6 (steps 4 and 6),
`models/validation_models/`.

## Files to create
```
tools/stub_tools/
├── __init__.py
├── stub_generator.py      ← generates backend stub specifications
└── stub_server.py         ← runs a simple HTTP stub server for validation
tools/log_replay_tools/
├── __init__.py
├── log_parser.py          ← parses legacy WSBCC log files
└── replay_case_builder.py ← builds LogReplayCase records from parsed logs
```

## `stub_generator.py`

```python
def generate_stub_spec(
    operation_id: str,
    db_lookups: list[DbLookupRequirement],
    routing_plan: RoutingPlan
) -> StubSpec:
    """
    Generates a stub specification for an operation's backend dependencies.

    For each DbLookupRequirement: create a stub entry returning a fixed test value.
    For each opStep that calls a backend service (HTTP/SOAP): create a stub entry.

    Stub entries have: endpoint, method, request_pattern, response_body, scenario.
    Multiple scenarios: one for success RC path, one for each error RC path.
    """
```

## `stub_server.py`

```python
def start_stub_server(stub_spec: StubSpec, port: int) -> StubServerHandle:
    """
    Starts an HTTP server that serves stub responses matching StubSpec.
    Returns a handle with stop() and get_call_log() methods.
    Uses Python's built-in http.server — no external dependencies.
    """
```

## `log_parser.py`

```python
def parse_wsbcc_log(log_file_path: str) -> list[dict]:
    """
    Parses a WSBCC server log file.
    Extracts: timestamp, operation_name, channel, request_xml, response_xml.
    Returns list of parsed log entries.
    Skips unparseable lines with a warning.
    """
```

## `replay_case_builder.py`

```python
def build_replay_cases(
    log_entries: list[dict],
    operation_id: str,
    max_cases: int = 10
) -> list[LogReplayCase]:
    """
    Filters log entries for the given operation_id.
    Selects up to max_cases entries covering:
    - At least one success response
    - At least one error response (if present in logs)
    - Representative variety of inputs
    Returns list of LogReplayCase records.
    """
```

## Tests
`tests/test_stub_tools.py`:
- stub_generator produces one scenario per routing terminal path.
- stub_server returns correct response for matching request.
- log_parser extracts operation_name and XML from sample log line.
- replay_case_builder selects success + error cases.
