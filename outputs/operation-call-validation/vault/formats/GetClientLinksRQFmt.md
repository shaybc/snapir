# GetClientLinksRQFmt

---
entity_type: format
entity_id: GetClientLinksRQFmt
conversion_status: not_started
shared: true
used_by_operations:
  - GetClientLinksOp
  - GetClientOverviewOp
  - ValidateClientLinksOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientLinks.xml
source_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88
---

## Structure
```xml
<CCXML dataName="GetClientLinks">
  <CCString dataName="ClientId">
  </CCString>
    decorator: <CCMandatory/>
  <CCString dataName="BankId">
  </CCString>
    decorator: <CCPadding length="4" padChar="0"/>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCMandatory](formats/CCMandatory.md)
- [CCPadding](formats/CCPadding.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- com.ibm.il.dse.cc.decorator.CCMandatory
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)

## Inferred External Dependencies
- None
