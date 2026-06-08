# Prompt 10 — `conversion_tools/` Part 1: channel_filter + decorator_chain_resolver

## Context
Stage 3, Step 11 (first two tools). All Stage 1-2 tools exist.
These are the simplest conversion tools — implement and test them first.
Everything else depends on channel filtering working correctly.

## Reference
`Implementation_plan_V8.md` section 11 (conversion_tools definitions),
`wsbcc_developer_manual_v2.md` section 4 (onlyFor), section 5 (decorator chains).

## Files to create
```
tools/conversion_tools/channel_filter_tool.py
tools/conversion_tools/decorator_chain_resolver_tool.py
```

## `channel_filter_tool.py`

```python
def filter_opsteps_for_channel(
    conn,
    operation_id: str,
    channel: str,
    run_id: str
) -> tuple[list[str], list[ExcludedOpStep]]:
    """
    Reads the opStep list for operation_id from source_artifacts.
    For each opStep: reads onlyFor from metadata_json.
    Included: onlyFor is None, blank, or contains channel (case-insensitive).
    Excluded: onlyFor is set and does not contain channel.

    Returns (included_opstep_ids_in_order, excluded_opsteps).
    Preserves the execution order from the operation's step list.

    IMPORTANT: onlyFor is an opStep-level attribute. An operation is never
    excluded by channel — only individual opSteps within it may be excluded.
    """
```

### onlyFor matching rules
- `onlyFor=None` or `onlyFor=""` → included (no restriction)
- `onlyFor="internet"` and channel="INTERNET" → included (case-insensitive)
- `onlyFor="IVR,internet"` and channel="INTERNET" → included (comma-separated)
- `onlyFor="IVR"` and channel="INTERNET" → excluded

## `decorator_chain_resolver_tool.py`

```python
def resolve_decorator_chains(
    format_vault_path: str
) -> list[tuple[str, list[str]]]:
    """
    Reads the ## Structure section of a format vault note.
    Parses the XML-like tag tree and finds all decorator entries.

    Decorator entries appear as lines starting with 'decorator: <tagName'
    immediately following a formatter tag line.

    Returns list of (formatter_node_identifier, [decorator_tag_names]).
    formatter_node_identifier = '{dataName}/{tagName}' e.g. 'ClientId/CCString'
    decorator_tag_names in the order they appear (forward order = format direction).

    Any formatter type can have decorators. No type restrictions.
    """

def get_decorator_chain_for_field(
    decorator_chains: list[tuple[str, list[str]]],
    field_name: str
) -> list[str]:
    """
    Returns the decorator chain for a specific field name.
    Searches decorator_chains for an entry whose formatter_node_identifier
    starts with field_name + '/'.
    Returns empty list if no decorators found.
    """
```

### Parsing rules for Structure section
```
<CCXML dataName="GetClientLinks">     <- CCXML container (may have children)
  <CCString dataName="ClientId"/>     <- formatter with dataName="ClientId"
  decorator: <nilDecorator/>          <- decorator for ClientId/CCString
  <CCDate dataName="RequestDate" .../>
  decorator: <RemoveLeadingZerosDecorator/>   <- first decorator for RequestDate
  decorator: <CCPadding padChar="0" length="9"/>  <- second decorator
</CCXML>
```

Identify the formatter from the line before the decorator line(s).
A formatter line has the form: `  <TagName dataName="..."`.
A decorator line has the form: `  decorator: <TagName`.
Multiple consecutive decorator lines belong to the immediately preceding formatter.

## Rules
- channel_filter_tool must NEVER exclude an operation — only opSteps.
- decorator_chain_resolver_tool parses the vault Structure section text,
  not raw WSBCC XML.
- Both tools are deterministic — no LLM.
- decorator chains are in forward order (format direction). Calling code
  that needs unformat direction must reverse the list.

## Tests
`tests/test_channel_filter_tool.py`:
- opStep with onlyFor=None → included.
- opStep with onlyFor="IVR" and channel="INTERNET" → excluded.
- opStep with onlyFor="internet,IVR" and channel="INTERNET" → included (case-insensitive).
- Execution order of included steps is preserved.

`tests/test_decorator_chain_resolver.py`:
- CCString with nilDecorator: returns [("ClientId/CCString", ["nilDecorator"])].
- CCDate with two decorators: returns both in order.
- CCXML with no decorators: returns empty list for that node.
- Field with no decorators: get_decorator_chain_for_field returns [].
