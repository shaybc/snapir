# GetClientAccountsRQFmt

---
entity_type: format
entity_id: GetClientAccountsRQFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientAccounts.xml
source_hash: c6d10b4ed4d931e4e2933f6afeb7d68804cec3db9f1e488ea24a74b332d31bb8
---

## Structure
```xml
<CCXML dataName="GetClientAccounts">
  <CCString dataName="ClientId">
  </CCString>
    decorator: <CCMandatory/>
  <CCString dataName="SessionToken">
  </CCString>
    decorator: <CCMandatory/>
  <CCBoolean dataName="IncludeInactive">
  </CCBoolean>
    decorator: <nilDecorator/>
  <CCString dataName="BankId">
  </CCString>
    decorator: <CCPadding length="4" padChar="0"/>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCMandatory](formats/CCMandatory.md)
- [CCBoolean](formats/CCBoolean.md)
- [nilDecorator](formats/nilDecorator.md)
- [CCPadding](formats/CCPadding.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- com.ibm.il.dse.cc.decorator.CCMandatory
- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)

## Inferred External Dependencies
- None
