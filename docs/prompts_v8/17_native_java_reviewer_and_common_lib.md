# Prompt 17 — `NativeJavaReviewAgent` + `common_lib_tools/`

## Context
Stage 4, Step 15-16. Converter agents (14-16) exist.
NativeJavaReviewAgent reviews each converted file. common_lib_tools promotes
validated shared artifacts and converts framework tags eagerly.

## Reference
`Implementation_plan_V8.md` section 5 Phase 3 (Code review and compile),
section 5 Phase 3 (common-lib promotion rule: used_by_validated_operations >= 2).

## Files to create
```
agents/source_conversion/native_java_reviewer/
├── __init__.py
└── agent.py
tools/common_lib_tools/
├── __init__.py
├── promotion.py
└── build.py
```

## `NativeJavaReviewAgent` instruction

```
You are reviewing a converted native Java class against its original IBM source.

REVIEW_KIND: {review_kind}  (ibm_java | xml_fmtdef_dto | context_class)
ORIGINAL_SOURCE: {original_source}
CONVERTED_CLASS: {converted_java}
PARENT_CLASS: {parent_class}
BEHAVIOR_TYPE: {behavior_types}

Check ALL of the following:
1. NO IBM imports remain (com.ibm.*, javax.ejb.*, org.omg.* etc.)
2. Business logic is preserved EXACTLY from original execute() or equivalent.
3. All return code values are unchanged.
4. All setter methods are present (from original XML attribute handling).
5. Context field access is correctly rewritten (setValueAt -> typed setter).
6. For dto review: no logic in the DTO, no DB calls, CCTableFormat absent.
7. For context review: flat class, no inheritance, all fields present.

Output JSON:
{
  "issues": ["description of each issue found"],
  "confidence": "high|medium|low",
  "review_status": "approved|needs_revision|needs_human_review"
}
- approved: no issues found, confidence=high or medium
- needs_revision: issues found but fixable by the converter agent
- needs_human_review: issues found that require human judgment
  (confidence=low, or IBM logic that cannot be automatically converted)

Output ONLY the JSON. No explanation.
```

## Review dispatch
```python
def dispatch_reviews_for_batch(conn, run_id: str, batch_converted_ids: list[str]):
    """
    For each converted artifact in the batch:
    - Reads original source and converted class.
    - Calls NativeJavaReviewAgent.
    - On approved: marks native_java_artifacts.review_status=approved.
    - On needs_revision: feeds issues back to the originating converter agent.
    - On needs_human_review: sets needs_human_review + blocking_reason.
    """
```

## `common_lib_tools/promotion.py`

Already defined in Prompt 03 (`artifact_registry_tools/promotion.py`).
Here, add the `promote_to_common_lib` trigger that is called after each
`mark_validated` call in `artifact_registry_tools`:

```python
def maybe_promote(conn, component_id: str, common_lib_root: str, run_id: str):
    """
    Called after every mark_validated.
    If used_by_validated_operations >= 2: call promote_to_common_lib.
    """
```

## `common_lib_tools/build.py`
```python
def run_common_lib_build(common_lib_root: str) -> JavaBuildResult:
    """Runs 'mvn install' on the common-lib project. Returns build result."""

def convert_framework_tags(
    conn, tag_registry_channel: str, common_lib_root: str,
    composer_root: str, run_id: str
) -> list[str]:
    """
    Eagerly converts all formatter/decorator classes from the XML channel
    (CCString, CCDate, CCXML, CCIColl, nilDecorator, etc.) before batch 1.
    Each class is cleaned by IbmJavaCleanerAgent logic (runs synchronously here,
    not as an ADK task) and installed to common-lib.
    Returns list of converted FQCNs.
    """
```

## Human Gate 2 output
After reviewing all pilot batch converted files:
```
=== Human Gate 2 ===
Converted files reviewed: {N}
Approved: {N}
Needs revision (auto-retry pending): {N}
Needs human review: {N}

common-lib build: PASSED | FAILED
Framework tags converted: {N}

Sample files for review: [paths]
Approve to continue to Phase 4 (operation assembly)? (yes/no)
```

## Tests
`tests/test_native_java_reviewer.py` (mock LLM):
- IBM import in converted class → issues list contains the import.
- Missing setter → issues list mentions it.
- approved output → native_java_artifacts.review_status=approved.
- promote: used_by=1 → not promoted. used_by=2 → promoted + mvn install called.
