# Prompt 03 — `artifact_registry_tools/`

## Context
Stage 1, Step 3. Models (01) and state_store_tools (02) exist.
This package manages component reuse — the cache that prevents re-converting
already-validated artifacts. It is the gatekeeper for lazy, closure-driven
conversion.

## Reference
`Implementation_plan_V8.md` sections 10 (hash comparison point) and 5 Phase 3
(lazy conversion rule).

## Package structure

```
tools/artifact_registry_tools/
├── __init__.py
├── reuse_resolver.py      ← hash comparison, cache hit/miss decision
├── component_registry.py  ← CRUD for component_registry table
└── promotion.py           ← promote_to_common_lib, convert_framework_tags
```

## `reuse_resolver.py`

Implement exactly as specified in plan section 10:

```python
from models.registry_models import ArtifactReuseDecision

def resolve_component_reuse(
    conn,
    artifact_kind: str,
    logical_id: str,
    source_hash: str,
    channel: str,
    target_language: str,
    schema_version: str = "v1"
) -> ArtifactReuseDecision:
    """
    Checks component_registry for an existing validated artifact.
    Returns:
      should_reuse=True  if found, source_hash matches, status=validated
      should_reuse=False with reason in: not_in_registry | hash_mismatch | status_invalid
    """
```

The `reason` field drives logging and metrics — always populate it.

## `component_registry.py`

```python
def register_component(conn, record: ComponentRegistryRecord) -> None: ...
def get_component(conn, artifact_kind, logical_id,
                  target_language, schema_version) -> ComponentRegistryRecord | None: ...
def mark_validated(conn, component_id: str) -> None: ...
def increment_used_by_validated(conn, component_id: str) -> None: ...
def get_used_by_validated_count(conn, component_id: str) -> int: ...
def list_shared_candidates(conn, run_id: str,
                           min_used_by: int = 2) -> list[ComponentRegistryRecord]: ...
```

## `promotion.py`

```python
def promote_to_common_lib(
    conn,
    component_id: str,
    common_lib_root: str,
    run_id: str
) -> bool:
    """
    Promotes a validated artifact to common-lib when
    used_by_validated_operations >= 2.
    Copies artifact to common_lib_root/src/...
    Runs 'mvn install' on common-lib.
    Returns True if promotion succeeded.
    Raises if mvn install fails — do not silently swallow build errors.
    """

def convert_framework_tags(
    conn,
    tag_registry_channel: str,  # "XML" — the shared base channel
    common_lib_root: str,
    run_id: str
) -> list[str]:
    """
    Eagerly converts all built-in formatter and decorator classes from the
    XML channel (CCString, CCDate, CCXML, CCIColl, nilDecorator, CCPadding, etc.)
    before batch 1 runs.
    These go directly into common-lib without the >= 2 promotion gate.
    Returns list of converted FQCNs.
    """
```

## Rules
- `resolve_component_reuse` is called at the start of every conversion task,
  before any LLM call.
- `promote_to_common_lib` must check the `>= 2` threshold before promoting —
  never promote an artifact used by only one validated operation.
- `convert_framework_tags` is called once at the start of Phase 3, before any
  batch runs. It bypasses the `>= 2` gate because framework tags are universal.

## Tests
`tests/test_artifact_registry.py`:
- Cache miss on empty registry returns `should_reuse=False, reason="not_in_registry"`.
- After registering + marking validated: cache hit returns `should_reuse=True`.
- Hash mismatch after update: returns `should_reuse=False, reason="hash_mismatch"`.
- `promote_to_common_lib` with `used_by_validated_operations=1` does not promote.
- `promote_to_common_lib` with `used_by_validated_operations=2` promotes.
