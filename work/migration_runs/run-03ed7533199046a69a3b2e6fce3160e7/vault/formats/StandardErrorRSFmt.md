# StandardErrorRSFmt

---
entity_type: format
entity_id: StandardErrorRSFmt
conversion_status: not_started
shared: true
used_by_operations:
  - GetAccountDetailsOp
  - GetClientAccountsOp
  - GetClientLinksOp
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_XML\src\Xml Definition\Channel\XML\defaultFile\dseformat.xml
source_hash: c1896648708bc8b2fcef4dfea7b956580922d56268c6a6947c807ccec9063f52
---

## Structure
```xml
<CCXML dataName="ErrorReply">
  <CCString dataName="ErrorCategory"/>
  <CCString dataName="ErrorNumber"/>
  <CCString dataName="ErrorDescription">
  </CCString>
    decorator: <nilDecorator/>
  <CCString dataName="RequestId"/>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [nilDecorator](formats/nilDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)

## Inferred External Dependencies
- None
