# GetClientAccountsIvrRQFmt

---
entity_type: format
entity_id: GetClientAccountsIvrRQFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetClientAccounts.xml
source_hash: 9dcc938f33cbdec98354dbeb023d9574ed8f2df9476a13e128ee8f7b171d76dc
---

## Structure
```xml
<CCXML dataName="GetClientAccounts">
  <CCString dataName="ClientId">
  </CCString>
    decorator: <CCMandatory/>
  <CCString dataName="Pin">
  </CCString>
    decorator: <CCMandatory/>
    decorator: <MaskLogDecorator/>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCMandatory](formats/CCMandatory.md)
- [MaskLogDecorator](formats/MaskLogDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- com.ibm.il.dse.cc.decorator.CCMandatory
- [com.ibm.il.dse.cc.decorator.MaskLogDecorator](classes/com/ibm/il/dse/cc/decorator/MaskLogDecorator.md)

## Inferred External Dependencies
- None
