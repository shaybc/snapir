# LinkEntryFmt

---
entity_type: format
entity_id: LinkEntryFmt
conversion_status: not_started
shared: false
used_by_operations: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\defaultFile\dseformat.xml
source_hash: d7f422f36bb086464fe11e6974af0d2817462ce519006e86c4f8fd221c30b65d
---

## Structure
```xml
<CCXML dataName="Link">
  <CCString dataName="LinkId">
  </CCString>
    decorator: <CCMandatory/>
  <CCString dataName="LinkUrl"/>
  <CCTableFormat dataName="LinkDescription" fromColumn="DESCRIPTION" fromTable="LINK_TYPES" keyValue="LinkId"/>
  <CCBoolean dataName="IsExternal"/>
  <CCString dataName="IconCode">
  </CCString>
    decorator: <nilDecorator/>
</CCXML>
```

## Database Lookups
> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.

- CCTableFormat: fromTable `LINK_TYPES`, fromColumn `DESCRIPTION`, keyValue `LinkId`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCMandatory](formats/CCMandatory.md)
- [CCTableFormat](formats/CCTableFormat.md)
- [CCBoolean](formats/CCBoolean.md)
- [nilDecorator](formats/nilDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- com.ibm.il.dse.cc.decorator.CCMandatory
- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)
- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)

## Inferred External Dependencies
- API/Service
- Database
