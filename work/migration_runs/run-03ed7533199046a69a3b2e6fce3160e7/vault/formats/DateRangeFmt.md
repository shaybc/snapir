# DateRangeFmt

---
entity_type: format
entity_id: DateRangeFmt
conversion_status: not_started
shared: false
used_by_operations: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_XML\src\Xml Definition\Channel\XML\defaultFile\dseformat.xml
source_hash: c1896648708bc8b2fcef4dfea7b956580922d56268c6a6947c807ccec9063f52
---

## Structure
```xml
<CCXML dataName="DateRange" transparent="true">
  <CCDate dataName="FromDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no">
  </CCDate>
    decorator: <nilDecorator/>
  <CCDate dataName="ToDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no">
  </CCDate>
    decorator: <nilDecorator/>
</CCXML>
```

## Serialization Notes
- This format contains CCXML serialization flags that affect the XML wire shape.
- `DateRange transparent=true`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCDate](formats/CCDate.md)
- [nilDecorator](formats/nilDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCDate](classes/com/ibm/il/dse/cc/format/CCDate.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)

## Inferred External Dependencies
- None
