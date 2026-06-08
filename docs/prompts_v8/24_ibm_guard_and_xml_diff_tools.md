# Prompt 24 — `ibm_dependency_guard_tool` + `xml_diff_tool`

## Context
Stage 7, Step 22. Validation infrastructure before validation agents are built.
These two deterministic tools are used inside JavaValidationAgent.

## Reference
`Implementation_plan_V8.md` section 5 Phase 6 (steps 2 and 4),
`constants.py` FORBIDDEN_DEPENDENCIES.

## Files to create
```
tools/validation_tools/ibm_dependency_guard_tool.py
tools/validation_tools/xml_diff_tool.py
tools/validation_tools/__init__.py
```

## `ibm_dependency_guard_tool.py`

```python
def scan_for_ibm_dependencies(
    generated_path: str,
    forbidden_patterns: list[str]
) -> list[str]:
    """
    Recursively scans all .java files under generated_path.
    For each file: checks all import statements and string literals.
    Returns list of (file_path, line_number, matched_pattern) tuples as strings.
    Empty list = clean.
    """

def scan_source(
    java_source: str,
    forbidden_patterns: list[str]
) -> list[str]:
    """Scans a single Java source string. Returns matched patterns."""

def is_clean(generated_path: str, forbidden_patterns: list[str]) -> bool:
    """Returns True if no forbidden patterns found."""
```

Matching rules:
- Match is substring, case-insensitive.
- Only scan import statements and string literal lines.
- A class.forName("com.ibm...") in a string literal must be caught.

## `xml_diff_tool.py`

```python
def compare_xml(
    expected_xml: str,
    actual_xml: str,
    ignore_whitespace: bool = True,
    ignore_element_order: bool = False
) -> XmlDiffResult:
    """
    Compares two XML strings structurally and by value.
    Returns XmlDiffResult with passed=True if equivalent.

    Comparison levels:
    1. Schema level: same elements, same attributes, same hierarchy.
    2. Value level: same text content per element.
    3. Attribute value level.

    ignore_whitespace: True by default — trim and normalise whitespace.
    ignore_element_order: False by default — order matters for WSBCC responses.
    """

def generate_diff_report(result: XmlDiffResult) -> str:
    """Human-readable diff report for the Gate report."""
```

Use Python's `xml.etree.ElementTree` for parsing.
Do not use lxml (offline enterprise environment — may not be available).

## Tests
`tests/test_validation_tools.py`:
- ibm_guard: finds "import com.ibm.dse.base.CCOperationStep" as IBM.
- ibm_guard: clean Spring Boot service returns empty list.
- ibm_guard: class.forName("com.ibm...") in string literal is caught.
- xml_diff: identical XMLs → passed=True.
- xml_diff: different element value → passed=False, diff_count=1.
- xml_diff: extra element in actual → passed=False.
- xml_diff: whitespace difference with ignore_whitespace=True → passed=True.
