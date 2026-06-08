# Prompt 15 — `XmlToJavaConverterAgent`

## Context
Stage 4, Step 13. IbmJavaCleanerAgent (14) exists.
This agent converts WSBCC fmtDef XML into two outputs: a JAXB-annotated DTO
and a ServiceLayerRequirements specification.

## Reference
`Implementation_plan_V8.md` section 5 Phase 3 (XML fmtDef definitions section),
`skills/xml_to_java_skills/fmtdef_to_jaxb.md`,
`wsbcc_developer_manual_v2.md` sections 6, 7 (formats, decorators).

## Files to create
```
agents/source_conversion/xml_to_java_converter/
├── __init__.py
└── agent.py
```

## LLM instruction (XML_TO_JAVA_INSTRUCTION)

```
You are converting a WSBCC fmtDef XML definition into:
1. A JAXB-annotated Java DTO class (pure data carrier, NO logic)
2. A ServiceLayerRequirements JSON spec

INPUT DOCUMENTS:
FORMAT_ID: {format_id}
FMTDEF_XML: the raw fmtDef XML
STRUCTURE_SECTION: the resolved tag tree from the vault ## Structure section
  (includes decorator lines already resolved — read them directly)
SERIALIZATION_NOTES: transparent/unnamed CCXML flags
DATABASE_LOOKUPS: CCTableFormat DB lookup specifications

JAXB DTO RULES (non-negotiable):
1. The DTO is a pure data carrier. No logic. No DB calls. No validation.
2. Use @XmlRootElement(name="...") on the root element.
3. Use @XmlElement(name="...") on each field.
4. Use @XmlElementWrapper + @XmlElement on List fields (from CCIColl tags).
5. transparent="true" on a CCXML element means OMIT that wrapper element
   from the JAXB mapping — its children appear at the parent level.
6. CCTableFormat nodes: DO NOT add a field for the looked-up value in the DTO.
   Instead add it to ServiceLayerRequirements.db_lookups. The service layer
   will populate this field before serialization.
7. Field types: CCString->String, CCDate->String (formatted),
   CCBoolean->boolean, NumberFormat->String, CCIColl->List<NestedDtoType>.
8. All fields private with getters and setters.
9. Include a no-argument constructor.
10. Output the DTO class only. No imports beyond JAXB. No explanation.

SERVICE LAYER REQUIREMENTS RULES:
For each decorator chain in STRUCTURE_SECTION:
- field_name: the dataName of the formatter
- format_direction: list of addDecoration calls in forward order
- unformat_direction: list of removeDecoration calls in REVERSE order
  (last decorator first)
For each DATABASE_LOOKUP entry:
- Move to db_lookups in ServiceLayerRequirements
- The service layer must call the DB and populate this field before
  serialization; the DTO does not contain this lookup logic.

Output TWO items separated by the marker <<<SLR_START>>>:
1. The complete JAXB DTO Java source
<<<SLR_START>>>
2. The ServiceLayerRequirements as JSON
```

## Output parsing
Split LLM output on `<<<SLR_START>>>`.
Part 1: JAXB DTO Java source → write to file, compile.
Part 2: Parse JSON → ServiceLayerRequirements model → store in DB.

## Tools

```python
def get_format_conversion_task(conn, task_id: str) -> ConversionTaskPacket: ...

def submit_jaxb_dto(
    conn, task_id: str, java_source: str, output_path: str, run_id: str
) -> str:
    """Writes DTO, runs javac, returns 'compiled' | 'compile_failed'."""

def submit_service_layer_requirements(
    conn, format_id: str, channel: str, slr: ServiceLayerRequirements, run_id: str
) -> None:
    """Stores ServiceLayerRequirements in service_layer_requirements table."""
```

## Retry logic
Same pattern as IbmJavaCleanerAgent:
- Compile failure → include error in retry prompt.
- MAX_RETRIES exceeded → blocking_reason=compile_failed.
- Parsing failure of SLR JSON → retry with explicit JSON format reminder.

## Tests
`tests/test_xml_to_java_converter.py`:
- transparent CCXML omits wrapper element from DTO.
- CCTableFormat appears in SLR db_lookups, not in DTO.
- CCIColl generates List field with @XmlElementWrapper.
- Decorator chain in SLR: format_direction in forward order.
- Decorator chain in SLR: unformat_direction in reverse order.
