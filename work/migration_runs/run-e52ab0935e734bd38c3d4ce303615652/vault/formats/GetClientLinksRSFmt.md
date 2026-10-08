# GetClientLinksRSFmt

---
entity_type: format
entity_id: GetClientLinksRSFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetClientLinksOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientLinks.xml
source_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88
---

## Structure
```xml
<CCXML dataName="GetClientLinksResponse" transparent="true">
  <CCString dataName="ClientId"/>
  <CCIColl dataName="Links" times="*">
    <CCXML dataName="Link">
      <CCString dataName="LinkId">
      </CCString>
        decorator: <CCMandatory/>
      <CCTableFormat dataName="LinkDescription" fromColumn="DESCRIPTION" fromTable="LINK_TYPES" keyValue="LinkId">
      </CCTableFormat>
        decorator: <nilDecorator/>
      <CCString dataName="LinkUrl"/>
      <CCBoolean dataName="IsExternal"/>
      <CCString dataName="IconCode">
      </CCString>
        decorator: <nilDecorator/>
    </CCXML>
  </CCIColl>
</CCXML>
```

## Serialization Notes
- This format contains CCXML serialization flags that affect the XML wire shape.
- `GetClientLinksResponse transparent=true`

## Database Lookups
> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.

- CCTableFormat: fromTable `LINK_TYPES`, fromColumn `DESCRIPTION`, keyValue `LinkId`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCIColl](formats/CCIColl.md)
- [CCMandatory](formats/CCMandatory.md)
- [CCTableFormat](formats/CCTableFormat.md)
- [nilDecorator](formats/nilDecorator.md)
- [CCBoolean](formats/CCBoolean.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.format.CCIColl](classes/com/ibm/il/dse/cc/format/CCIColl.md)
- com.ibm.il.dse.cc.decorator.CCMandatory
- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)
- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)

## Inferred External Dependencies
- Database
- API/Service
