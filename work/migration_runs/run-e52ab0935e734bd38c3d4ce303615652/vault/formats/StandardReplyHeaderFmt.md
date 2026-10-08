# StandardReplyHeaderFmt

---
entity_type: format
entity_id: StandardReplyHeaderFmt
conversion_status: not_started
shared: false
used_by_operations: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_XML\src\Xml Definition\Channel\XML\defaultFile\dseformat.xml
source_hash: c1896648708bc8b2fcef4dfea7b956580922d56268c6a6947c807ccec9063f52
---

## Structure
```xml
<CCXML dataName="ReplyHeader" transparent="true">
  <CCString dataName="RequestId"/>
  <CCSysTimeDate dataName="ReplyTimestamp"/>
  <CCConstant dataName="Status" value="SUCCESS"/>
</CCXML>
```

## Serialization Notes
- This format contains CCXML serialization flags that affect the XML wire shape.
- `ReplyHeader transparent=true`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCSysTimeDate](formats/CCSysTimeDate.md)
- [CCConstant](formats/CCConstant.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- com.ibm.il.dse.cc.format.CCSysTimeDate
- com.ibm.il.dse.cc.format.CCConstant

## Inferred External Dependencies
- None
