# MoneyAmountFmt

---
entity_type: format
entity_id: MoneyAmountFmt
conversion_status: not_started
shared: false
used_by_operations: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_XML\src\Xml Definition\Channel\XML\defaultFile\dseformat.xml
source_hash: c1896648708bc8b2fcef4dfea7b956580922d56268c6a6947c807ccec9063f52
---

## Structure
```xml
<CCXML dataName="Amount" transparent="true">
  <NumberFormat dataName="Value" showDecimalsSep="yes" showThousandsSep="no"/>
  <CCString dataName="Currency">
  </CCString>
    decorator: <CCPadding length="3" padChar=" "/>
</CCXML>
```

## Serialization Notes
- This format contains CCXML serialization flags that affect the XML wire shape.
- `Amount transparent=true`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [NumberFormat](formats/NumberFormat.md)
- [CCString](formats/CCString.md)
- [CCPadding](formats/CCPadding.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)

## Inferred External Dependencies
- None
