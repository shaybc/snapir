# GetAccountBalanceRQFmt

---
entity_type: format
entity_id: GetAccountBalanceRQFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetAccountBalanceOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetAccountBalance.xml
source_hash: 0fb403fd7c6dea2ff8390f4079959769b0e3c15a2c3538965bbb50b481dd4c2e
---

## Structure
```xml
<CCXML dataName="GetAccountBalance">
  <CCString dataName="ClientId">
  </CCString>
    decorator: <CCMandatory/>
  <CCString dataName="AccountNumber">
  </CCString>
    decorator: <CCMandatory/>
    decorator: <CCPadding length="10" padChar="0"/>
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
- [CCPadding](formats/CCPadding.md)
- [MaskLogDecorator](formats/MaskLogDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- com.ibm.il.dse.cc.decorator.CCMandatory
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.decorator.MaskLogDecorator](classes/com/ibm/il/dse/cc/decorator/MaskLogDecorator.md)

## Inferred External Dependencies
- None
